"""
build_hcmc_roads.py
Fetch HCMC road network from Overpass API, build graph directly into data_hcmc/.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import joblib

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = BASE_DIR / "data_hcmc"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

HIGHWAY_TYPES = [
    "motorway", "trunk", "primary", "secondary",
    "tertiary", "residential", "unclassified",
    "living_street", "service",
]
HCMC_BBOX = (10.75, 106.55, 10.95, 106.85)

LOS_TRAVEL_TIME_FACTOR = {
    "A": 1.0, "B": 1.15, "C": 1.35,
    "D": 1.65, "E": 2.2, "F": 4.0,
}

MAX_VEL_MAP = {
    "motorway": 100, "trunk": 80, "primary": 60,
    "secondary": 50, "tertiary": 40,
    "residential": 30, "unclassified": 30,
    "living_street": 20, "service": 20,
}
STREET_LEVEL_MAP = {
    "motorway": 1, "trunk": 1, "primary": 2,
    "secondary": 3, "tertiary": 3,
    "residential": 4, "unclassified": 4,
    "living_street": 5, "service": 5,
}


def make_query():
    bbox = HCMC_BBOX
    ways = "\n  ".join(
        f'way["highway"="{h}"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});'
        for h in HIGHWAY_TYPES
    )
    return (
        f"[out:json][timeout:300];\n"
        f"(\n  {ways}\n);\n"
        f"out body;\n"
        f">;\n"
        f"out skel qt;"
    )


def fetch_overpass() -> dict:
    import requests
    query = make_query()
    for url in OVERPASS_URLS:
        try:
            print(f"  Fetching from {url}...")
            resp = requests.post(
                url, data={"data": query}, timeout=240,
                headers={"User-Agent": "ITS-Traffic-Dashboard/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
            ways = [e for e in data.get("elements", []) if e.get("type") == "way"]
            nodes = [e for e in data.get("elements", []) if e.get("type") == "node"]
            print(f"  {len(ways)} ways, {len(nodes)} nodes received")
            return data
        except Exception as e:
            print(f"  Failed ({url}): {e}")
            time.sleep(3)
    return None


def parse_to_graph(data: dict):
    """Build nodes_df, seg_df, streets_df, coords_array, and G from Overpass data."""
    elements = data.get("elements", [])
    nodes_map = {}
    for el in elements:
        if el.get("type") == "node":
            nodes_map[el["id"]] = {"lat": el["lat"], "lon": el["lon"]}

    ways_by_id = {el["id"]: el for el in elements if el.get("type") == "way"}
    node_set = set(nodes_map.keys())
    R = 6371000

    node_rows = []
    seg_rows = []
    seen_nodes = set()

    for way_id, el in ways_by_id.items():
        tags = el.get("tags", {})
        highway = tags.get("highway", "unclassified")
        name = tags.get("name") or tags.get("ref") or f"Road-{way_id}"
        node_refs = el.get("nodes", [])
        if len(node_refs) < 2:
            continue

        valid_refs = [n for n in node_refs if n in node_set]
        if len(valid_refs) < 2:
            continue

        max_vel = MAX_VEL_MAP.get(highway, 40)
        ms = tags.get("maxspeed", "")
        if ms and "km/h" in ms:
            try:
                max_vel = float(ms.replace("km/h", "").strip())
            except ValueError:
                pass

        lanes = 2
        try:
            lanes = int(tags.get("lanes", 2))
        except (ValueError, TypeError):
            pass

        street_level = STREET_LEVEL_MAP.get(highway, 3)

        for i in range(len(valid_refs) - 1):
            s_id, e_id = valid_refs[i], valid_refs[i + 1]
            s_n, e_n = nodes_map[s_id], nodes_map[e_id]

            lat1, lon1 = math.radians(s_n["lat"]), math.radians(s_n["lon"])
            lat2, lon2 = math.radians(e_n["lat"]), math.radians(e_n["lon"])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
            length_m = 2 * R * math.asin(math.sqrt(a))

            if length_m < 3:
                continue

            free_flow_tt = length_m / max(max_vel / 3.6, 0.1)

            seg_rows.append({
                "segment_id": len(seg_rows) + 1,
                "s_node_id": int(s_id),
                "e_node_id": int(e_id),
                "length": round(length_m, 2),
                "max_velocity": float(max_vel),
                "street_level": street_level,
                "highway": highway,
                "street_name": name,
                "lanes": lanes,
                "free_flow_tt": round(free_flow_tt, 2),
                "oneway": tags.get("oneway", "no"),
                "surface": tags.get("surface", "asphalt"),
            })

            for nid, nd in [(s_id, s_n), (e_id, e_n)]:
                if nid not in seen_nodes:
                    node_rows.append({
                        "node_id": int(nid),
                        "lat": nd["lat"],
                        "lon": nd["lon"],
                    })
                    seen_nodes.add(nid)

    # Build NetworkX graph
    node_lat = {int(n["node_id"]): n["lat"] for n in node_rows}
    node_lon = {int(n["node_id"]): n["lon"] for n in node_rows}

    G = nx.MultiGraph(directed=False)
    for n in node_rows:
        G.add_node(int(n["node_id"]), lat=n["lat"], lon=n["lon"])

    for row in seg_rows:
        s, e = int(row["s_node_id"]), int(row["e_node_id"])
        G.add_edge(
            s, e,
            segment_id=row["segment_id"],
            length=row["length"],
            max_velocity=row["max_velocity"],
            street_level=row["street_level"],
            street_name=row["street_name"],
            highway=row["highway"],
            lanes=row["lanes"],
            free_flow_tt=row["free_flow_tt"],
            los="B",
            confidence=0.5,
            los_weight=row["free_flow_tt"] * LOS_TRAVEL_TIME_FACTOR["B"],
            lat1=node_lat.get(s, 0), lon1=node_lon.get(s, 0),
            lat2=node_lat.get(e, 0), lon2=node_lon.get(e, 0),
        )

    nodes_df = pd.DataFrame(node_rows)
    seg_df = pd.DataFrame(seg_rows)
    coords_array = nodes_df[["node_id", "lat", "lon"]].values.astype(np.float64)

    # Streets table
    streets_df = pd.DataFrame([
        {"street_name": row["street_name"], "highway": row["highway"]}
        for row in seg_rows
    ]).drop_duplicates(subset=["street_name"])

    return nodes_df, seg_df, streets_df, coords_array, G


def save_cache(nodes_df, seg_df, streets_df, coords_array, G):
    nodes_df.to_parquet(CACHE_DIR / "nodes.parquet", index=False, compression="snappy")
    seg_df.to_parquet(CACHE_DIR / "segments.parquet", index=False, compression="snappy")
    streets_df.to_parquet(CACHE_DIR / "streets.parquet", index=False, compression="snappy")
    np.save(CACHE_DIR / "node_coords.npy", coords_array)
    joblib.dump(G, CACHE_DIR / "graph_full.joblib", compress=3)

    meta = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "graph": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges()},
        "shapes": {
            "nodes": len(nodes_df),
            "segments": len(seg_df),
            "coords_indexed": len(coords_array),
            "streets": len(streets_df),
        },
    }
    with open(CACHE_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"  Saved:")
    print(f"    nodes.parquet       — {len(nodes_df):,} nodes")
    print(f"    segments.parquet    — {len(seg_df):,} segments")
    print(f"    streets.parquet     — {len(streets_df):,} streets")
    print(f"    node_coords.npy     — {len(coords_array):,} coords")
    print(f"    graph_full.joblib   — {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    print(f"    metadata.json")


def build_and_cache():
    t0 = time.time()
    print("=" * 60)
    print("  XAY DUNG DO THI GIAO THONG TP.HCM TU OVERPASS API")
    print("=" * 60)

    print("\nFetching road network from Overpass...")
    data = fetch_overpass()
    if data is None:
        print("FETCH FAILED — check network and Overpass API status.")
        return

    print("\nParsing and building graph...")
    nodes_df, seg_df, streets_df, coords_array, G = parse_to_graph(data)

    if G.number_of_nodes() == 0:
        print("No nodes in graph!")
        return

    print(f"\nGraph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    print("\nSaving cache to data_hcmc/...")
    save_cache(nodes_df, seg_df, streets_df, coords_array, G)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  XONG TRONG {elapsed:.1f}s")
    print(f"  {G.number_of_nodes():,} nut, {G.number_of_edges():,} canh")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    build_and_cache()
