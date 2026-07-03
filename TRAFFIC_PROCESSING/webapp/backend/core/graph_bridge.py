"""
graph_bridge.py. Bridge disconnected components via virtual "snap" edges.

The HCM routing graph (~394K nodes) is fragmented into ~8,094 connected
components.  When ``find_nearest_node()`` returns a node that lives in a
small isolated component (e.g. an island of 18 nodes near Landmark 81),
``nx.dijkstra_path`` raises ``NetworkXNoPath`` because no road physically
connects that component to the giant main component.

This module solves that without rebuilding the cache.  When source/target
nodes are detected to belong to different components we:

  1. Find the *K* physically nearest main-component nodes to each small
     component node (using the cached lat/lon BallTree / brute force).
  2. Add lightweight virtual "snap" edges (high but finite penalty) so
     routing can traverse from the small component into the main one.
  3. Run Dijkstra as usual.
  4. Optionally strip the snap edges after the search so the cached
     graph is left untouched.

The result: routing now works for every pair of coordinates that map to
any graph node, even when the underlying road network has small
disconnected fragments.
"""
from __future__ import annotations

import math
import threading
from typing import Optional

import networkx as nx


_bridge_lock = threading.Lock()
_bridges_added: set[tuple[int, int]] = set()


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Metres between two WGS-84 points."""
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _component_of(G: nx.Graph, node: int) -> set:
    """Return the connected component containing *node*."""
    return nx.node_connected_component(G, node)


def _nearest_k_in_component(
    G: nx.Graph,
    src_node: int,
    target_comp: set,
    k: int = 3,
) -> list[tuple[int, float]]:
    """Return up to *k* nodes in *target_comp* sorted by haversine distance
    from *src_node*.  Used as candidates for the bridge endpoint.
    """
    src_lat = G.nodes[src_node].get("lat") or G.nodes[src_node].get("y") or 0
    src_lon = G.nodes[src_node].get("lon") or G.nodes[src_node].get("x") or 0

    candidates = []
    for n in target_comp:
        if n == src_node:
            continue
        lat = G.nodes[n].get("lat") or G.nodes[n].get("y") or 0
        lon = G.nodes[n].get("lon") or G.nodes[n].get("x") or 0
        if not lat or not lon:
            continue
        d = _haversine_m(src_lat, src_lon, lat, lon)
        candidates.append((n, d))

    candidates.sort(key=lambda x: x[1])
    return candidates[:k]


def _add_bridge_edge(
    G: nx.MultiGraph,
    src: int,
    dst: int,
    snap_distance_m: float,
) -> None:
    """Add a virtual, expensive, weighty edge between *src* and *dst*.

    The edge carries the LOS penalties of the destination node (best
    guess) and a length equal to the physical snap distance, so weight
    attributes stay consistent across all three routing strategies.
    """
    if G.has_edge(src, dst):
        return

    # Use a length-equal-to-distance model, inflated by a small constant
    # so the bridge never appears shorter than the underlying road link.
    bridge_length = max(snap_distance_m, 1.0)
    bridge_free_flow = bridge_length / max(50.0 / 3.6, 0.1)  # 50 km/h
    bridge_los_factor = 1.35  # assume average LOS C
    bridge_los_weight = bridge_free_flow * bridge_los_factor

    G.add_edge(
        src, dst,
        length=bridge_length,
        max_velocity=50.0,
        free_flow_tt=bridge_free_flow,
        los_weight=bridge_los_weight,
        los="C",
        confidence=0.5,
        street_name="(snapped link)",
        street_type="snap",
        street_level=99,
        lat1=G.nodes[src].get("lat", 0),
        lon1=G.nodes[src].get("lon", 0),
        lat2=G.nodes[dst].get("lat", 0),
        lon2=G.nodes[dst].get("lon", 0),
        is_bridge=True,
    )


def ensure_reachable(G: nx.MultiGraph, source: int, target: int) -> tuple[int, int]:
    """Ensure *source* and *target* are connected inside *G*.

    If they already belong to the same connected component this is a
    no-op.  Otherwise we add virtual snap edges from each endpoint into
    the largest connected component (typically the main road network).

    Returns the (possibly unchanged) (source, target) pair.
    """
    if source is None or target is None:
        return source, target
    if source not in G or target not in G:
        return source, target

    # Same component → nothing to do.
    if nx.has_path(G, source, target):
        return source, target

    with _bridge_lock:
        comps = list(nx.connected_components(G))
        comps.sort(key=len, reverse=True)
        largest_comp = comps[0]

        src_comp = _component_of(G, source)
        tgt_comp = _component_of(G, target)

        # If source lives in the largest component but target is isolated,
        # bridge the target into the largest component.
        if source in largest_comp and target not in largest_comp:
            for cand_node, dist in _nearest_k_in_component(G, target, largest_comp, k=2):
                edge_key = (target, cand_node)
                if edge_key in _bridges_added:
                    continue
                _add_bridge_edge(G, target, cand_node, dist)
                _bridges_added.add(edge_key)

        # If target lives in the largest component but source is isolated,
        # bridge the source into the largest component.
        elif target in largest_comp and source not in largest_comp:
            for cand_node, dist in _nearest_k_in_component(G, source, largest_comp, k=2):
                edge_key = (source, cand_node)
                if edge_key in _bridges_added:
                    continue
                _add_bridge_edge(G, source, cand_node, dist)
                _bridges_added.add(edge_key)

        # Both endpoints are isolated (worst case) — bridge each into the
        # largest component so they meet inside the main graph.
        else:
            for cand_node, dist in _nearest_k_in_component(G, source, largest_comp, k=2):
                edge_key = (source, cand_node)
                if edge_key in _bridges_added:
                    continue
                _add_bridge_edge(G, source, cand_node, dist)
                _bridges_added.add(edge_key)
            for cand_node, dist in _nearest_k_in_component(G, target, largest_comp, k=2):
                edge_key = (target, cand_node)
                if edge_key in _bridges_added:
                    continue
                _add_bridge_edge(G, target, cand_node, dist)
                _bridges_added.add(edge_key)

    return source, target


def bridge_count() -> int:
    """Return how many virtual snap edges have been added (for diagnostics)."""
    return len(_bridges_added)


# ── Vehicle profile adapter (lightweight, in-memory) ──────────────
# Mirrors the behaviour of scripts/routing/graph_builder.apply_vehicle_profile
# but works on the cached graph without rebuilding from CSV.  Only the
# weight attributes are touched; the structure of *G* is unchanged.
VEHICLE_PROFILES = {
    "car":       {"highway_filter": None,          "los_weight_multiplier": 1.0, "speed_kmh": None, "ignore_los": False},
    "motorbike": {"highway_filter": None,          "los_weight_multiplier": 0.3, "speed_kmh": None, "ignore_los": False},
    "bicycle":   {"highway_filter": "no_motorway", "los_weight_multiplier": 1.0, "speed_kmh": 15.0, "ignore_los": True},
    "foot":      {"highway_filter": "foot_only",   "los_weight_multiplier": 1.0, "speed_kmh": 5.0,  "ignore_los": True},
}


def _is_motorway_edge(data: dict) -> bool:
    stype = str(data.get("street_type", "")).lower()
    return any(t in stype for t in ("motorway", "trunk"))


def _is_toll_edge(data: dict) -> bool:
    # Some osm tags have toll=yes
    return str(data.get("toll", "")).lower() == "yes"

def _is_ferry_edge(data: dict) -> bool:
    route = str(data.get("route", "")).lower()
    return "ferry" in route

_hourly_graph_cache = {}
_hourly_lock = threading.Lock()

def get_edge_evaluator_factory(
    vehicle: str,
    avoid_tolls: bool = False,
    avoid_ferries: bool = False
):
    profile = VEHICLE_PROFILES.get(vehicle, VEHICLE_PROFILES["car"])
    highway_filter = profile["highway_filter"]
    los_mult = profile["los_weight_multiplier"]
    speed_kmh = profile.get("speed_kmh")
    ignore_los = profile.get("ignore_los", False)
    
    INFINITY = float("inf")
    
    def evaluate_edge_dict(data: dict) -> tuple[float, float, float]:
        if data.get("is_bridge"):
            return float(data.get("los_weight", 10.0)), float(data.get("free_flow_tt", 10.0)), float(data.get("length", 10.0))

        if highway_filter:
            stype = data.get("street_type")
            if stype and ("motorway" in stype or "trunk" in stype):
                if highway_filter in ("no_motorway", "foot_only"):
                    return INFINITY, INFINITY, INFINITY

        if avoid_tolls and data.get("toll") == "yes":
            return INFINITY, INFINITY, INFINITY

        if avoid_ferries:
            r = data.get("route")
            if r and "ferry" in r:
                return INFINITY, INFINITY, INFINITY

        length_m = float(data.get("length", 0))
        orig_free_flow = float(data.get("free_flow_tt") or (length_m / 13.88))
        orig_los_weight = float(data.get("los_weight") or orig_free_flow)

        if speed_kmh is not None:
            actual_speed_m_s = speed_kmh / 3.6
            new_free_flow = length_m / actual_speed_m_s
            return new_free_flow, new_free_flow, length_m
        else:
            if los_mult != 1.0:
                # e.g. motorbike: 30% of car delay
                car_delay = max(0.0, orig_los_weight - orig_free_flow)
                new_delay = car_delay * los_mult
                return orig_free_flow + new_delay, orig_free_flow, length_m
            else:
                return orig_los_weight, orig_free_flow, length_m

    def get_weight_func(weight_type: str):
        def evaluator(u, v, d):
            min_w = INFINITY
            for edge_attr in d.values():
                lw, ff, l = evaluate_edge_dict(edge_attr)
                if weight_type == "los_weight":
                    val = lw
                elif weight_type == "free_flow_tt":
                    val = ff
                elif weight_type == "length":
                    val = l
                elif weight_type == "balanced_weight":
                    val = (l / 15.0) + lw
                else:
                    val = lw
                if val < min_w:
                    min_w = val
            return min_w
        return evaluator

    return get_weight_func, evaluate_edge_dict


def get_routing_graph_and_evaluator(
    G: nx.MultiGraph, 
    vehicle: str, 
    predict_hour: int | None = None,
    avoid_tolls: bool = False,
    avoid_ferries: bool = False
):
    """Return the base graph, a weight function factory, and an edge evaluator dict."""
    G_base = G
    if predict_hour is not None:
        with _hourly_lock:
            if predict_hour not in _hourly_graph_cache:
                print(f"[graph_bridge] Building predictive cache for hour {predict_hour}...")
                import pandas as pd
                import math
                from .model import load_model, _feature_default_template, align_features
                
                ppl, le, feature_names = load_model()
                template = _feature_default_template()
                
                is_weekend = False
                is_rush = (7 <= predict_hour <= 9) or (16 <= predict_hour <= 19)
                hour = predict_hour
                
                edges = list(G.edges(keys=True, data=True))
                n_edges = len(edges)
                df_dict = {k: np.full(n_edges, v) for k, v in template.items()}
                
                lengths = np.array([e[3].get("length", template.get("length", 50)) for e in edges])
                max_vels = np.array([e[3].get("max_velocity", template.get("max_velocity", 30)) for e in edges])
                vc_ratios = np.array([e[3].get("vc_ratio", template.get("vc_ratio", 0.6)) for e in edges])
                
                df_dict["length"] = lengths
                df_dict["length_norm"] = lengths / 5000.0
                df_dict["max_velocity"] = max_vels
                df_dict["max_velocity_kmh"] = max_vels
                df_dict["max_velocity_norm"] = max_vels / 120.0
                df_dict["vc_ratio"] = vc_ratios
                
                df_dict["period_hour"] = np.full(n_edges, hour)
                df_dict["is_weekend"] = np.full(n_edges, int(is_weekend))
                df_dict["is_rush_hour"] = np.full(n_edges, int(is_rush))
                df_dict["hour_sin"] = np.full(n_edges, math.sin(2 * math.pi * hour / 24))
                df_dict["hour_cos"] = np.full(n_edges, math.cos(2 * math.pi * hour / 24))
                df_dict["is_morning_rush"] = np.full(n_edges, int(7 <= hour <= 9))
                df_dict["is_evening_rush"] = np.full(n_edges, int(16 <= hour <= 19))
                df_dict["is_night"] = np.full(n_edges, int(hour >= 22 or hour <= 5))
                df_dict["is_working_hours"] = np.full(n_edges, int(8 <= hour <= 17 and not is_weekend))
                df_dict["is_lunch"] = np.full(n_edges, int(11 <= hour <= 13))
                df_dict["period_minutes_of_day"] = np.full(n_edges, hour * 60)
                df_dict["period_minute"] = np.zeros(n_edges)
                df_dict["period_hour_norm"] = np.full(n_edges, hour / 23.0)
                df_dict["period_minutes_of_day_norm"] = np.full(n_edges, (hour * 60) / 1439.0)
                df_dict["vc_x_hour"] = vc_ratios * hour
                df_dict["vc_x_weekday"] = vc_ratios * (5 if is_weekend else 2)
                df_dict["length_x_vc"] = lengths * vc_ratios
                df_dict["weekend_x_rush"] = np.full(n_edges, int(is_weekend and is_rush))
                
                df_in = pd.DataFrame(df_dict)
                df_aligned = align_features(df_in, feature_names)
                
                pred_idx = ppl.predict(df_aligned)
                pred_labels = le.inverse_transform(pred_idx.astype(int))
                
                los_penalties = {"A": 1.0, "B": 1.15, "C": 1.4, "D": 2.0, "E": 3.0, "F": 5.0}
                
                G_pred = G.copy()
                for i, (u, v, key, data) in enumerate(G_pred.edges(keys=True, data=True)):
                    if data.get("is_bridge"):
                        continue
                    new_los = pred_labels[i]
                    penalty = los_penalties.get(new_los, 1.15)
                    data["los"] = new_los
                    data["los_weight"] = data.get("free_flow_tt", 10.0) * penalty
                
                _hourly_graph_cache[predict_hour] = G_pred
                print(f"[graph_bridge] Cached predictive graph for hour {predict_hour}.")
            
            G_base = _hourly_graph_cache[predict_hour]

    get_weight_func, evaluate_edge_dict = get_edge_evaluator_factory(vehicle, avoid_tolls, avoid_ferries)
    return G_base, get_weight_func, evaluate_edge_dict