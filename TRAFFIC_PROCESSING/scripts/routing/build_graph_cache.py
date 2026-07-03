"""
Automate Ho Chi Minh City traffic graph construction from raw data.
Uses NetworkX MultiGraph with BallTree support for nearest-neighbor search.

Cache directory structure:
  data_hcmc/
  ├── nodes.parquet        # Nodes: node_id, lat, lon (parquet)
  ├── segments.parquet     # Segments: segment_id, s_node, e_node, length, max_velocity, ...
  ├── streets.parquet      # Street lookup table
  ├── node_coords.npy     # Array (N, 3): [node_id, lat, lon] — for fast KD-tree search
  ├── graph_full.joblib    # Full NetworkX MultiGraph with edge attributes
  └── metadata.json        # Stats: num_nodes, num_edges, timestamp
"""
from __future__ import annotations

import json
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import joblib

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_RAW = BASE_DIR / "data_traffic"
CACHE_DIR = BASE_DIR / "data_hcmc"


def ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Thu muc cache: {CACHE_DIR}")


def load_raw_data():
    """Load raw CSV files with optimized data types."""
    print("Dang tai cac CSV goc...")

    nodes_df = pd.read_csv(DATA_RAW / "nodes.csv", low_memory=False)
    nodes_df = nodes_df.rename(columns={"_id": "node_id"})
    print(f"  nodes: {len(nodes_df):,} dong")

    seg_df = pd.read_csv(DATA_RAW / "segments.csv", low_memory=False)
    seg_df = seg_df.rename(columns={"_id": "segment_id"})
    print(f"  segments: {len(seg_df):,} dong")

    streets_df = pd.read_csv(DATA_RAW / "streets.csv", low_memory=False)
    streets_df = streets_df.rename(columns={"_id": "street_id"})
    print(f"  streets: {len(streets_df):,} dong")

    return nodes_df, seg_df, streets_df


def optimize_data_types(nodes_df, seg_df, streets_df):
    """Reduce numeric column sizes to save memory and improve speed."""
    for col in ["node_id"]:
        if col in nodes_df.columns:
            nodes_df[col] = nodes_df[col].astype(np.int64)

    for col in ["segment_id", "s_node_id", "e_node_id", "length", "street_id"]:
        if col in seg_df.columns:
            seg_df[col] = seg_df[col].astype(np.float64).astype("Int64")

    for col in ["long", "lat"]:
        if col in nodes_df.columns:
            nodes_df[col] = nodes_df[col].astype(np.float32)

    if "max_velocity" in seg_df.columns:
        seg_df["max_velocity"] = seg_df["max_velocity"].astype(np.float32)

    for col in ["street_id"]:
        if col in streets_df.columns:
            streets_df[col] = streets_df[col].astype(np.int64)

    return nodes_df, seg_df, streets_df


def save_parquet_cache(nodes_df, seg_df, streets_df):
    """Save processed data as Parquet (faster than CSV)."""
    print("Dang luu Parquet cache...")

    nodes_df.to_parquet(CACHE_DIR / "nodes.parquet", index=False, compression="snappy")
    seg_df.to_parquet(CACHE_DIR / "segments.parquet", index=False, compression="snappy")
    streets_df.to_parquet(CACHE_DIR / "streets.parquet", index=False, compression="snappy")

    print("  [OK] nodes.parquet")
    print("  [OK] segments.parquet")
    print("  [OK] streets.parquet")


def build_coordinate_index(nodes_df):
    """Build KD-tree search array from node coordinates."""
    print("Dang xay dung chi muc toa do nut...")

    valid = nodes_df.dropna(subset=["long", "lat"])
    valid = valid[valid["long"] != 0]
    valid = valid[valid["lat"] != 0]

    coords = valid[["node_id", "lat", "long"]].values.astype(np.float64)
    coords = coords[coords[:, 0].argsort()]

    np.save(CACHE_DIR / "node_coords.npy", coords)
    print(f"  [OK] node_coords.npy — {len(coords):,} nut co toa do")

    return coords


def build_graph(seg_df, coords_array):
    """Build NetworkX graph and save as joblib."""
    print("Dang xay dung do thi NetworkX...")

    G = nx.MultiGraph(directed=False)

    for row in coords_array:
        G.add_node(int(row[0]), lat=float(row[1]), lon=float(row[2]))

    print(f"  So nut do thi: {G.number_of_nodes():,}")

    node_lat = {int(row[0]): float(row[1]) for row in coords_array}
    node_lon = {int(row[0]): float(row[2]) for row in coords_array}

    added = 0
    skipped = 0
    for _, row in seg_df.iterrows():
        try:
            s = int(row["s_node_id"])
            e = int(row["e_node_id"])
            length = float(row["length"])
            max_vel = float(row.get("max_velocity", 50))
            street_level = int(row.get("street_level", 3))
            street_name = str(row.get("street_name", ""))
            street_type = str(row.get("street_type", ""))
            seg_id = int(row["segment_id"])

            if max_vel <= 0:
                max_vel = 50.0

            free_flow_tt = length / (max_vel / 3.6)

            lat1 = node_lat.get(s, 0.0)
            lon1 = node_lon.get(s, 0.0)
            lat2 = node_lat.get(e, 0.0)
            lon2 = node_lon.get(e, 0.0)

            los_factor = 1.15

            G.add_edge(
                s, e,
                segment_id=seg_id,
                length=length,
                max_velocity=max_vel,
                street_level=street_level,
                street_name=street_name,
                street_type=street_type,
                free_flow_tt=free_flow_tt,
                los="B",
                confidence=0.5,
                los_weight=free_flow_tt * los_factor,
                lat1=lat1, lon1=lon1,
                lat2=lat2, lon2=lon2,
            )
            added += 1
        except (ValueError, TypeError, KeyError):
            skipped += 1
            continue

    print(f"  So canh da them: {added:,} (bo qua: {skipped:,})")
    print(f"  Do thi: {G.number_of_nodes():,} nut, {G.number_of_edges():,} canh")

    graph_path = CACHE_DIR / "graph_full.joblib"
    joblib.dump(G, graph_path, compress=3)
    graph_size = graph_path.stat().st_size / 1e6
    print(f"  [OK] graph_full.joblib ({graph_size:.1f} MB)")

    return G


def save_metadata(nodes_df, seg_df, coords_array, G):
    """Save cache metadata."""
    meta = {
        "created_at": datetime.now().isoformat(),
        "source_data": {
            "nodes_raw": str(DATA_RAW / "nodes.csv"),
            "segments_raw": str(DATA_RAW / "segments.csv"),
            "streets_raw": str(DATA_RAW / "streets.csv"),
        },
        "shapes": {
            "nodes": int(len(nodes_df)),
            "segments": int(len(seg_df)),
            "coords_indexed": int(len(coords_array)),
        },
        "graph": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "is_directed": G.is_directed(),
        },
        "cache_files": [
            "nodes.parquet",
            "segments.parquet",
            "streets.parquet",
            "node_coords.npy",
            "graph_full.joblib",
            "metadata.json",
        ],
    }
    with open(CACHE_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"  [OK] metadata.json")


def build_cache():
    """Full cache construction pipeline."""
    t0 = time.time()
    print("=" * 60)
    print("  XAY DUNG CACHE DO THI GIAO THONG TP.HCM")
    print("=" * 60)

    ensure_cache_dir()

    nodes_df, seg_df, streets_df = load_raw_data()

    nodes_df, seg_df, streets_df = optimize_data_types(nodes_df, seg_df, streets_df)

    save_parquet_cache(nodes_df, seg_df, streets_df)

    coords_array = build_coordinate_index(nodes_df)

    G = build_graph(seg_df, coords_array)

    save_metadata(nodes_df, seg_df, coords_array, G)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  DA XAY DUNG CACHE TRONG {elapsed:.1f}s")
    print(f"  Vi tri: {CACHE_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    build_cache()
