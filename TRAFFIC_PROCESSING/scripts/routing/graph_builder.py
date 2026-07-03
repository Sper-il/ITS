"""
graph_builder.py — Build Ho Chi Minh City traffic graph.
Load from cache (Parquet + joblib graph) when available; build from raw CSV otherwise.
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import networkx as nx
import joblib

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_RAW = BASE_DIR / "data_traffic"
CACHE_DIR = BASE_DIR / "data_hcmc"


LOS_TRAVEL_TIME_FACTOR = {
    "A": 1.0, "B": 1.15, "C": 1.35,
    "D": 1.65, "E": 2.2, "F": 4.0,
}

# Spatial index using BallTree for O(log n) nearest-neighbor search.
# Falls back to O(n) brute force when sklearn is unavailable.
class SpatialIndex:
    def __init__(self, node_ids: list, lats: np.ndarray, lons: np.ndarray):
        self._ids = np.array(node_ids, dtype=np.int64)
        self._lats = np.asarray(lats, dtype=np.float64)
        self._lons = np.asarray(lons, dtype=np.float64)
        self._tree = None
        self._use_tree = False

        try:
            from sklearn.neighbors import BallTree
            coords = np.radians(np.column_stack([lats, lons]))
            self._tree = BallTree(coords, metric="haversine")
            self._use_tree = True
        except ImportError:
            self._use_tree = False

    def find_neighbors(self, lat: float, lon: float, max_dist_km: float = 10.0) -> Optional[int]:
        if self._use_tree and self._tree is not None:
            point = np.radians([[lat, lon]])
            radius = max_dist_km / 6371.0
            idx = self._tree.query_radius(point, r=radius)[0]
            if len(idx) == 0:
                return None
            lat_cand = np.radians(self._lats[idx])
            lon_cand = np.radians(self._lons[idx])
            lat_q = np.radians(lat)
            lon_q = np.radians(lon)
            dlat = lat_cand - lat_q
            dlon = lon_cand - lon_q
            hav = np.sin(dlat / 2) ** 2 + np.cos(lat_q) * np.cos(lat_cand) * np.sin(dlon / 2) ** 2
            dists = 2 * 6371 * np.arcsin(np.sqrt(np.clip(hav, 0, 1)))
            best = idx[np.argmin(dists)]
            return int(self._ids[best])
        else:
            min_dist = float("inf")
            best = None
            for i in range(len(self._ids)):
                dlat = self._lats[i] - lat
                dlon = self._lons[i] - lon
                dist_deg = (dlat**2 + dlon**2)**0.5
                dist_km = dist_deg * 111.0
                if dist_km < min_dist:
                    min_dist = dist_km
                    best = self._ids[i]
            if min_dist > max_dist_km:
                return None
            return int(best)


def load_from_cache():
    """
    Load graph and data from pre-built cache.
    Returns (nodes_df, seg_df, streets_df, coords_array, G, metadata) or None if cache is missing.
    """
    cache_files = [
        CACHE_DIR / "nodes.parquet",
        CACHE_DIR / "segments.parquet",
        CACHE_DIR / "streets.parquet",
        CACHE_DIR / "node_coords.npy",
        CACHE_DIR / "graph_full.joblib",
        CACHE_DIR / "metadata.json",
    ]

    if not all(f.exists() for f in cache_files):
        return None

    nodes_df = pd.read_parquet(CACHE_DIR / "nodes.parquet")
    seg_df = pd.read_parquet(CACHE_DIR / "segments.parquet")
    streets_df = pd.read_parquet(CACHE_DIR / "streets.parquet")
    coords_array = np.load(CACHE_DIR / "node_coords.npy")
    G = joblib.load(CACHE_DIR / "graph_full.joblib")
    with open(CACHE_DIR / "metadata.json", "r", encoding="utf-8") as f:
        import json
        meta = json.load(f)

    print(f"[CACHE] Da tai graph: {G.number_of_nodes():,} nut, {G.number_of_edges():,} canh")
    return nodes_df, seg_df, streets_df, coords_array, G, meta


def build_from_scratch_and_cache():
    """
    Build everything from raw CSV, save to cache, return same format as load_from_cache().
    Only runs when cache is missing.
    """
    print("[CACHE] Khong tim thay cache. Dang xay dung tu CSV goc...")

    from scripts.routing.build_graph_cache import (
        load_raw_data, optimize_data_types, save_parquet_cache,
        build_coordinate_index, build_graph, save_metadata,
        ensure_cache_dir,
    )

    ensure_cache_dir()
    nodes_df, seg_df, streets_df = load_raw_data()
    nodes_df, seg_df, streets_df = optimize_data_types(nodes_df, seg_df, streets_df)
    save_parquet_cache(nodes_df, seg_df, streets_df)
    coords_array = build_coordinate_index(nodes_df)
    G = build_graph(seg_df, coords_array)
    save_metadata(nodes_df, seg_df, coords_array, G)

    import json
    with open(CACHE_DIR / "metadata.json", "r", encoding="utf-8") as f:
        meta = json.load(f)

    return nodes_df, seg_df, streets_df, coords_array, G, meta


def get_cache_data():
    """
    Main entry point. Returns (nodes_df, seg_df, streets_df, coords_array, G, meta).
    Uses existing cache if available, otherwise builds and saves cache first.
    """
    cached = load_from_cache()
    if cached is not None:
        return cached
    return build_from_scratch_and_cache()


_spatial_index = None


def _build_spatial_index(G: nx.MultiGraph) -> SpatialIndex:
    """Build spatial index from nodes in the largest connected component."""
    global _spatial_index
    if _spatial_index is not None:
        return _spatial_index

    comps = list(nx.connected_components(G))
    largest_cc = max(comps, key=len)
    print(f"[SpatialIndex] Su dung thanh phan lien thong lon: {len(largest_cc):,} nut (trong {G.number_of_nodes():,} nut)")

    node_ids, lats, lons = [], [], []
    for nid in largest_cc:
        attrs = G.nodes[nid]
        g_lat = attrs.get("lat", 0)
        g_lon = attrs.get("lon", 0)
        if g_lat and g_lon:
            node_ids.append(int(nid))
            lats.append(float(g_lat))
            lons.append(float(g_lon))

    _spatial_index = SpatialIndex(node_ids, np.array(lats), np.array(lons))
    return _spatial_index


def load_graph(use_cache: bool = True) -> nx.MultiGraph:
    """
    Load the traffic graph.
    - use_cache=True (default): try cache first, fall back to building from CSV + caching.
    - use_cache=False: always build from raw CSV.
    Returns a NetworkX MultiGraph.
    """
    if use_cache:
        result = load_from_cache()
        if result is not None:
            G = result[4]
            _fix_missing_velocities(G)
            return G

    _, _, _, _, G, _ = build_from_scratch_and_cache()
    _fix_missing_velocities(G)
    return G


def _fix_missing_velocities(G: nx.MultiGraph) -> nx.MultiGraph:
    """
    Fix NaN free_flow_tt / los_weight by computing from missing max_velocity in raw data.
    Assign default speed based on road level.
    """
    ROAD_LEVEL_SPEEDS = {
        1: 80.0,
        2: 60.0,
        3: 40.0,
        4: 30.0,
        5: 20.0,
    }
    patched = 0
    for u, v, key, data in G.edges(keys=True, data=True):
        ff = data.get("free_flow_tt", 0)
        if ff is None or (isinstance(ff, float) and ff != ff):
            length = float(data.get("length", 0))
            sl = int(data.get("street_level", 3))
            max_vel = ROAD_LEVEL_SPEEDS.get(sl, 40.0)
            free_flow_tt = length / max(max_vel / 3.6, 0.1)
            data["free_flow_tt"] = free_flow_tt
            los_factor = LOS_TRAVEL_TIME_FACTOR.get(data.get("los", "B"), 1.0)
            data["los_weight"] = free_flow_tt * los_factor
            data["max_velocity"] = max_vel
            patched += 1
    if patched > 0:
        print(f"[PATCH] Da sua {patched:,} canh co velocity NaN")
    return G


def find_nearest_node(
    G: nx.MultiGraph,
    lat: float,
    lon: float,
    max_dist_km: float = 10.0,
) -> Optional[int]:
    """
    Find the nearest node to coordinates (lat, lon) in the graph.
    Uses BallTree spatial index for O(log n) search.
    Falls back to O(n) brute force when sklearn is unavailable.
    """
    idx = _build_spatial_index(G)
    return idx.find_neighbors(lat, lon, max_dist_km)


def get_graph_stats(G: nx.MultiGraph) -> dict:
    """Return basic statistics about the graph."""
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "connected_components": nx.number_connected_components(G),
        "is_directed": G.is_directed(),
    }


def add_los_to_graph(
    G: nx.MultiGraph,
    los_predictions: pd.DataFrame,
    segment_id_col: str = "segment_id",
    los_col: str = "LOS_pred",
    confidence_col: str = "confidence",
) -> nx.MultiGraph:
    """
    Attach predicted LOS to graph edges.
    Recalculates los_weight based on LOS factor.
    """
    los_map = {}
    for _, row in los_predictions.iterrows():
        seg_id = int(row[segment_id_col])
        los = str(row.get(los_col, "B"))
        conf = float(row.get(confidence_col, 0.5))
        los_map[seg_id] = {"los": los, "confidence": conf}

    for u, v, key, data in G.edges(keys=True, data=True):
        seg_id = data.get("segment_id")
        if seg_id in los_map:
            info = los_map[seg_id]
            data["los"] = info["los"]
            data["confidence"] = info["confidence"]
        else:
            data["los"] = "B"
            data["confidence"] = 0.5

        los_factor = LOS_TRAVEL_TIME_FACTOR.get(data["los"], 1.0)
        data["los_weight"] = data["free_flow_tt"] * los_factor
        data["congestion_penalty"] = los_factor

    return G


def apply_vehicle_profile(
    G: nx.MultiGraph,
    vehicle_key: str,
) -> nx.MultiGraph:
    """
    Return a COPY of *G* with weights adjusted for *vehicle_key*.

    Edge cases handled:
    - Unknown vehicle_key  -> returns a shallow copy with no changes.
    - Bicycle             -> motorway edges get weight = inf (impassable).
    - Foot                -> motorway/trunk edges get weight = inf (impassable).
    - All vehicles        -> los_weight multiplied by los_weight_multiplier.
    """
    VEHICLE_PROFILES = {
        "car":       {"max_velocity_kmh": 50, "highway_filter": None,        "los_weight_multiplier": 1.0},
        "motorbike": {"max_velocity_kmh": 40, "highway_filter": None,        "los_weight_multiplier": 0.9},
        "bicycle":   {"max_velocity_kmh": 18, "highway_filter": "no_motorway","los_weight_multiplier": 1.2},
        "foot":      {"max_velocity_kmh":  5, "highway_filter": "foot_only", "los_weight_multiplier": 1.0},
    }

    profile = VEHICLE_PROFILES.get(vehicle_key)
    if profile is None:
        return G.copy()

    highway_filter = profile["highway_filter"]
    los_mult = profile["los_weight_multiplier"]

    G_out = G.copy()

    for u, v, key, data in G_out.edges(keys=True, data=True):
        stype = str(data.get("street_type", "")).lower()
        is_motorway = any(t in stype for t in ("motorway", "trunk"))

        if highway_filter == "no_motorway" and is_motorway:
            data["los_weight"] = float("inf")
            data["free_flow_tt"] = float("inf")
            data["length"] = float("inf")
            continue

        if highway_filter == "foot_only" and is_motorway:
            data["los_weight"] = float("inf")
            data["free_flow_tt"] = float("inf")
            data["length"] = float("inf")
            continue

        data["los_weight"] = float(data.get("los_weight", 0)) * los_mult
