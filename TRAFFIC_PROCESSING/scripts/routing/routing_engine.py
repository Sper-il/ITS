"""
routing_engine.py — Route finding utilities with multiple optimization strategies.
Supports: shortest distance, fastest time, least congestion (LOS-aware).
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import networkx as nx


@dataclass
class RouteResult:
    """Route finding result."""
    path: list[int]
    total_distance_m: float
    total_travel_time_s: float
    edges: list[dict]
    los_distribution: dict[str, int]
    avg_confidence: float
    geometry_route: list[tuple[float, float]]
    strategy: str


# Routing strategy definitions for multi-route comparison (Sprint 1).
# Each entry: (display_name, weight_attribute_on_edge)
ROUTING_STRATEGIES = [
    ("Ít kẹt nhất", "los_weight"),   # least congestion (LOS-aware)
    ("Nhanh nhất",  "free_flow_tt"),  # fastest free-flow travel time
    ("Ngắn nhất",   "length"),        # shortest physical distance
]


def calc_los_weight(length_m: float, max_velocity_kmh: float, los: str) -> float:
    """Calculate edge weight (travel time) from predicted LOS."""
    FACTOR = {
        "A": 1.0, "B": 1.15, "C": 1.35,
        "D": 1.65, "E": 2.2, "F": 4.0,
    }
    factor = FACTOR.get(los, 1.0)
    free_flow_tt = length_m / max(max_velocity_kmh / 3.6, 0.1)
    return free_flow_tt * factor


def routing_dijkstra(
    G: nx.MultiGraph,
    source: int,
    target: int,
    weight: str = "free_flow_tt",
) -> tuple[list[int], float, float]:
    """
    Simple Dijkstra routing (using NetworkX).

    Returns: (node_list, total_distance_m, total_time_s)
    """
    try:
        path = nx.dijkstra_path(G, source, target, weight=weight)
        dist = nx.dijkstra_path_length(G, source, target, weight="length")
        time_s = nx.dijkstra_path_length(G, source, target, weight=weight)
        return path, dist, time_s
    except nx.NetworkXException:
        # Catch NoPath, NodeNotFound, and any other NX error.
        return [], 0.0, 0.0


def routing_astar_los(
    G: nx.MultiGraph,
    source: int,
    target: int,
    lattr: str = "lat",
    lonattr: str = "lon",
) -> list[int]:
    """
    A* routing with Euclidean distance heuristic.
    Default weight = free_flow_tt.
    """
    def haversine_heuristic(u, v):
        try:
            lat_u, lon_u = G.nodes[u][lattr], G.nodes[u][lonattr]
            lat_v, lon_v = G.nodes[v][lattr], G.nodes[v][lonattr]
            dlat = math.radians(lat_v - lat_u)
            dlon = math.radians(lon_v - lon_u)
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat_u)) * math.cos(math.radians(lat_v)) * math.sin(dlon / 2) ** 2
            c = 2 * math.asin(math.sqrt(max(0.0, min(1.0, a))))
            return 6_371_000.0 * c
        except Exception:
            return 0

    try:
        path = nx.astar_path(
            G, source, target,
            heuristic=haversine_heuristic,
            weight="free_flow_tt",
        )
        return path
    except nx.NetworkXException:
        # Catch NoPath, NodeNotFound, and any other NX error.
        return []


def find_all_paths(
    G: nx.MultiGraph,
    source: int,
    target: int,
    *,
    start_coord: Optional[tuple[float, float]] = None,
    end_coord: Optional[tuple[float, float]] = None,
    strategies: Optional[list[tuple[str, any]]] = None,
    edge_evaluator: Optional[callable] = None,
) -> list[RouteResult]:
    """
    Find alternative routes using multiple strategies.

    Default strategies (defined in ROUTING_STRATEGIES):
      1. "Ít kẹt nhất" -- los_weight  (least congestion / LOS-aware)
      2. "Nhanh nhất"  -- free_flow_tt (fastest free-flow time)
      3. "Ngắn nhất"   -- length      (shortest physical distance)

    Parameters
    ----------
    G
        The routing graph.
    source, target
        Origin and destination node IDs.
    start_coord, end_coord
        Optional (lat, lon) pair to extend geometry to exact user-clicked points.
    strategies
        Override list of (display_name, weight_key) tuples.  When omitted the
        module-level ROUTING_STRATEGIES constant is used, yielding all 3 routes.
    """
    results = []

    # Guard against stale node ids (e.g. spatial index built against a
    # previous graph object) so the UI does not 500 with NetworkXNoPath /
    # NodeNotFound when source/target don't belong to the current graph.
    # Also guard against G being None / empty so the UI never crashes with
    # `TypeError: argument of type 'NoneType' is not iterable`.
    if (
        G is None
        or G.number_of_nodes() == 0
        or source is None
        or target is None
    ):
        return results
    try:
        _src_ok = int(source) in G
        _tgt_ok = int(target) in G
    except Exception:
        return results
    if not (_src_ok and _tgt_ok):
        return results

    # Use override strategies if provided, otherwise fall back to module constant
    _strategies = strategies if strategies is not None else ROUTING_STRATEGIES

    seen_paths = {}

    for strategy_name, weight_key in _strategies:
        def heuristic(u, v):
            try:
                lat_u = G.nodes[u].get('lat', G.nodes[u].get('y'))
                lon_u = G.nodes[u].get('lon', G.nodes[u].get('x'))
                lat_v = G.nodes[v].get('lat', G.nodes[v].get('y'))
                lon_v = G.nodes[v].get('lon', G.nodes[v].get('x'))
                if lat_u is None or lon_u is None or lat_v is None or lon_v is None:
                    return 0
                dist_m = math.hypot(lat_v - lat_u, (lon_v - lon_u) * 0.98) * 111139.0
                if weight_key == 'length' or strategy_name == "Ngắn nhất":
                    return dist_m
                return dist_m / 30.0
            except Exception:
                return 0

        try:
            path = nx.astar_path(G, source, target, heuristic=heuristic, weight=weight_key)
        except nx.NetworkXException:
            # Catches NetworkXNoPath, NodeNotFound, and any other NX
            # exception so a stale spatial index never crashes the UI.
            continue
            
        path_tuple = tuple(path)
        if path_tuple in seen_paths:
            existing = seen_paths[path_tuple]
            if strategy_name not in existing.strategy:
                existing.strategy += f" & {strategy_name}"
            continue

        total_dist = 0.0
        total_time = 0.0
        los_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
        edges_info = []
        geometry = []

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge_data_map = G[u][v]
            first_key = next(iter(edge_data_map))
            ed = edge_data_map[first_key]

            if edge_evaluator:
                lw, ff, l = edge_evaluator(ed)
                length = l
                free_flow = ff
                real_time = lw
                los = ed.get("los", "B")
                conf = float(ed.get("confidence", 0.5))
            else:
                length = float(ed.get("length", 0))
                free_flow = float(ed.get("free_flow_tt", 0))
                los = ed.get("los", "B")
                conf = float(ed.get("confidence", 0.5))
                real_time = ed.get("los_weight")
                if real_time is None or (isinstance(real_time, float) and real_time != real_time):
                    real_time = free_flow
            total_time += real_time
            total_dist += length

            los_dist[los] = los_dist.get(los, 0) + 1

            lat1 = ed.get("lat1") or G.nodes[u].get('lat', G.nodes[u].get('y'))
            lon1 = ed.get("lon1") or G.nodes[u].get('lon', G.nodes[u].get('x'))
            lat2 = ed.get("lat2") or G.nodes[v].get('lat', G.nodes[v].get('y'))
            lon2 = ed.get("lon2") or G.nodes[v].get('lon', G.nodes[v].get('x'))
            
            edge_geometry = []
            if "geometry" in ed:
                try:
                    coords = list(ed["geometry"].coords)
                    edge_geometry = [(pt[1], pt[0]) for pt in coords]
                except Exception:
                    edge_geometry = [(lat1, lon1), (lat2, lon2)]
            else:
                edge_geometry = [(lat1, lon1), (lat2, lon2)]

            edges_info.append({
                "from": u,
                "to": v,
                "length_m": length,
                "los": los,
                "confidence": conf,
                "street": ed.get("street_name", ""),
                "street_type": ed.get("street_type", ""),
                "travel_time_s": float(real_time),
                "lat1": lat1,
                "lon1": lon1,
                "lat2": lat2,
                "lon2": lon2,
                "street_name": ed.get("street_name", "unknown"),
                "geometry": edge_geometry,
            })
            
            # If the edge has a proper shapely geometry, we could use its coords here,
            # but for now we ensure at least the two endpoints are included.
            if lat1 and lon1:
                geometry.append((lat1, lon1))
            if lat2 and lon2:
                geometry.append((lat2, lon2))

        # Deduplicate geometry
        deduped_geo = []
        for pt in geometry:
            if not deduped_geo or pt != deduped_geo[-1]:
                deduped_geo.append(pt)

        # Extend geometry so polyline reaches the EXACT user-clicked start/end points
        if start_coord:
            deduped_geo.insert(0, start_coord)
        if end_coord:
            deduped_geo.append(end_coord)

        avg_conf = float(np.mean([e["confidence"] for e in edges_info])) if edges_info else 0.5

        res = RouteResult(
            path=path,
            total_distance_m=total_dist,
            total_travel_time_s=total_time,
            edges=edges_info,
            los_distribution=los_dist,
            avg_confidence=avg_conf,
            geometry_route=deduped_geo,
            strategy=strategy_name,
        )
        seen_paths[path_tuple] = res
        results.append(res)

    return results


def format_travel_time(seconds: float) -> str:
    """Format seconds -> 'Xm Ys' or 'Xh Ym'."""
    if seconds < 0 or seconds != seconds:
        return "N/A"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"


def format_distance(meters: float) -> str:
    """Format meters -> km."""
    if meters < 0 or meters != meters:
        return "N/A"
    if meters < 1000:
        return f"{int(meters)}m"
    return f"{meters / 1000:.2f}km"


def find_multi_leg_path(
    G: nx.MultiGraph,
    waypoints: list[tuple[float, float]],
    *,
    start_coord: Optional[tuple[float, float]] = None,
    end_coord: Optional[tuple[float, float]] = None,
) -> Optional[list[RouteResult]]:
    """
    Find a route through a sequence of waypoints.

    Iterates through consecutive pairs (start, wp1), (wp1, wp2), ...,
    (wpN, end) and calls ``find_all_paths`` for each leg.  Returns a list of
    RouteResult objects (one per leg) on success, or ``None`` if any leg
    fails to find a path.

    Parameters
    ----------
    G
        The routing graph.
    waypoints
        List of (lat, lon) tuples for each intermediate stop.
    start_coord
        (lat, lon) of the trip origin (used to extend geometry).
    end_coord
        (lat, lon) of the trip destination (used to extend geometry).

    Returns
    -------
    list[RouteResult] | None
        One RouteResult per leg, or None if any leg is unreachable.
    """
    from scripts.routing.graph_builder import find_nearest_node

    # Build the full ordered list of stop coords
    stops: list[tuple[tuple[float, float] | None, tuple[float, float] | None]] = []

    prev_coord: tuple[float, float] | None = start_coord
    for wp_coord in waypoints:
        stops.append((prev_coord, wp_coord))
        prev_coord = wp_coord
    # Final leg: last waypoint -> end
    stops.append((prev_coord, end_coord))

    legs: list[RouteResult] = []

    for leg_idx, (src_coord, dst_coord) in enumerate(stops):
        if src_coord is None or dst_coord is None:
            return None
        src_node = find_nearest_node(G, src_coord[0], src_coord[1])
        dst_node = find_nearest_node(G, dst_coord[0], dst_coord[1])
        if src_node is None or dst_node is None:
            return None
        if src_node == dst_node:
            return None

        leg_results = find_all_paths(
            G, src_node, dst_node,
            start_coord=src_coord if leg_idx == 0 else None,
            end_coord=dst_coord if leg_idx == len(stops) - 1 else None,
        )
        if not leg_results:
            return None
        legs.append(leg_results[0])

    return legs
