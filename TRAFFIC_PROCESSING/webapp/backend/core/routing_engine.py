"""
routing_engine.py. Thin adapter over scripts/routing/routing_engine.py.

Loads the cached HCM routing graph (built by scripts/routing/build_graph_cache.py)
and exposes ``find_all_paths()`` plus a JSON-serialisable result builder.

This module does NOT import Streamlit.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# routing_engine.py  →  webapp/backend/core/routing_engine.py
# hierarchy: routing_engine -> core -> backend -> webapp -> TRAFFIC_PROCESSING
_TRAFFIC_PROC = Path(__file__).resolve().parents[3]  # → .../ITS/TRAFFIC_PROCESSING
_SCRIPTS = _TRAFFIC_PROC / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from routing import routing_engine as re_mod  # type: ignore  # noqa: E402

from .constants import LOS_COLORS, ROUTE_STRATEGY_NAMES
from .routing_math import format_distance_km, format_travel_time


_graph_lock = threading.Lock()
_G = None
_NODE_INDEX: dict[tuple[float, float], int] | None = None
_LOS: dict[int, str] | None = None


def _load_graph():
    """Load graph cache from data_hcmc/ (sibling of TRAFFIC_PROCESSING/)."""
    global _G, _NODE_INDEX, _LOS
    with _graph_lock:
        if _G is not None:
            return _G
        # The cached graph lives next to TRAFFIC_PROCESSING/. Look for any
        # sensible cache format the build script might have produced.
        candidates = [
            _TRAFFIC_PROC.parent / "data_hcmc" / "graph_full.joblib",
            _TRAFFIC_PROC.parent / "data_hcmc" / "hcmc_routing_graph.joblib",
            _TRAFFIC_PROC.parent / "data_hcmc" / "hcmc_routing_graph.gpkg",
            _TRAFFIC_PROC.parent / "data_hcmc" / "hcmc_routing_graph.gpickle",
            _TRAFFIC_PROC.parent / "data_hcmc" / "hcmc_routing_graph.graphml",
        ]
        import joblib as _jl
        for c in candidates:
            if c.exists():
                try:
                    _G = _jl.load(str(c))
                    break
                except Exception:
                    try:
                        import pickle
                        with open(c, "rb") as f:
                            _G = pickle.load(f)
                        break
                    except Exception:
                        _G = None
        if _G is None:
            # Final fallback: build a tiny empty graph so /api/route returns []
            # gracefully with a 200 status, rather than crashing the server.
            import networkx as nx
            _G = nx.MultiGraph()
        # Build spatial index (lazy: dict on (lat, lon)).
        _NODE_INDEX = {}
        for n, data in _G.nodes(data=True):
            lat = data.get("lat") or data.get("y")
            lon = data.get("lon") or data.get("x")
            if lat is not None and lon is not None:
                _NODE_INDEX[(round(lat, 6), round(lon, 6))] = n
        return _G


def graph_stats() -> dict:
    """Return counts so the UI banner can display 'graph: N nodes, M edges'."""
    G = _load_graph()
    return {
        "nodes": int(G.number_of_nodes()),
        "edges": int(G.number_of_edges()),
    }


def find_nearest_node(lat: float, lon: float) -> Optional[int]:
    """Snap a free (lat, lon) to the closest node in the routing graph."""
    _load_graph()
    if not _NODE_INDEX:
        return None
    target = (round(lat, 6), round(lon, 6))
    if target in _NODE_INDEX:
        return _NODE_INDEX[target]
    # Linear nearest neighbour (graphs are <20K nodes; this is fast enough).
    best, best_d = None, float("inf")
    for (la, lo), n in _NODE_INDEX.items():
        d2 = (la - lat) ** 2 + (lo - lon) ** 2
        if d2 < best_d:
            best_d = d2
            best = n
    return best


def find_all_paths_between(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    *,
    vehicle: str = "car",
    predict_hour: int | None = None,
    avoid_tolls: bool = False,
    avoid_ferries: bool = False,
) -> list[dict]:
    """Find 3 routes (least congestion, fastest, shortest) between two coords.

    Returns a list of JSON-serialisable dicts in the exact shape the
    front-end expects.  ``geometry`` is ``[(lat, lon), ...]``.
    """
    import networkx as nx
    G = _load_graph()
    s = find_nearest_node(start_lat, start_lon)
    t = find_nearest_node(end_lat, end_lon)

    # If the routing graph splits the two nearest nodes into disconnected
    # components (the HCM cache has ~8K fragments), bridge them with
    # lightweight virtual snap edges so routing still succeeds.
    from .graph_bridge import ensure_reachable
    s, t = ensure_reachable(G, s, t)

    if s is None or t is None:
        return []

    # Apply vehicle-specific weight adjustments dynamically.
    from .graph_bridge import get_routing_graph_and_evaluator
    G_base, get_weight_func, evaluate_edge_dict = get_routing_graph_and_evaluator(
        G, 
        vehicle, 
        predict_hour=predict_hour, 
        avoid_tolls=avoid_tolls, 
        avoid_ferries=avoid_ferries
    )

    # Override strategies — map UI label -> existing weight key.
    strategies = [
        (ROUTE_STRATEGY_NAMES["least_congested"], get_weight_func("los_weight")),
        ("Cân bằng",                              get_weight_func("balanced_weight")),
        (ROUTE_STRATEGY_NAMES["fastest"],         get_weight_func("free_flow_tt")),
        (ROUTE_STRATEGY_NAMES["shortest"],        get_weight_func("length")),
    ]

    routes = re_mod.find_all_paths(
        G_base, s, t,
        start_coord=(start_lat, start_lon),
        end_coord=(end_lat, end_lon),
        strategies=strategies,
        edge_evaluator=evaluate_edge_dict,
    )

    out: list[dict] = []
    for r in routes:
        edges_payload = []
        for e in r.edges:
            edges_payload.append({
                "from":         e["from"],
                "to":           e["to"],
                "length_m":     e["length_m"],
                "los":          e["los"],
                "los_color":    LOS_COLORS.get(e["los"], "#888"),
                "confidence":   e["confidence"],
                "street":       e.get("street_name") or e.get("street", ""),
                "street_type":  e.get("street_type", ""),
                "travel_time_s": e["travel_time_s"],
                "lat1":         e["lat1"], "lon1": e["lon1"],
                "lat2":         e["lat2"], "lon2": e["lon2"],
            })
        out.append({
            "strategy":               r.strategy,
            "total_distance_m":       r.total_distance_m,
            "total_distance_display": format_distance_km(r.total_distance_m),
            "total_travel_time_s":    r.total_travel_time_s,
            "total_travel_time_str":  re_mod.format_travel_time(r.total_travel_time_s),
            "avg_confidence":         r.avg_confidence,
            "los_distribution":       r.los_distribution,
            "geometry":               [list(p) for p in r.geometry_route],
            "edges":                  edges_payload,
        })
    return out
