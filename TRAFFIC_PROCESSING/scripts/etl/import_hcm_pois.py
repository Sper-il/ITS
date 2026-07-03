# -*- coding: utf-8 -*-
"""
import_hcm_pois.py. ETL script that downloads the Geofabrik Ho Chi Minh City
PBF, extracts POI nodes/ways with pyrosm, and bulk-loads them into
data/hcm_poi.db via POIDatabase.

Run:
    python -m scripts.etl.import_hcm_pois

Target: 100,000+ POIs. If the initial filter set yields fewer, the script
expands to additional OSM tags until the target is reached.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PBF_URL = "https://download.geofabrik.de/asia/vietnam/ho-chi-minh-city-latest.osm.pbf"
PBF_SHA256 = "a1b2c3d4"  # placeholder; will verify after download if needed

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"
PBF_PATH = RAW_DIR / "hcm.osm.pbf"
DB_PATH = Path(__file__).resolve().parents[3] / "data" / "hcm_poi.db"

# HCM bounding box (approximate, covers the entire metro area)
HCM_BBOX = (10.35, 106.45, 10.95, 107.00)  # (min_lat, min_lon, max_lat, max_lon)

# ---- Phase 1: Core POI tag filters ----------------------------------------
# Each entry: (osm_key, osm_value, category, subcategory)
# 'amenity' / 'shop' / etc. are top-level categories.
POI_TAG_FILTERS_PHASE1: list[tuple[str, str, str, str]] = [
    # amenity
    ("amenity", "*", "amenity", "{value}"),
    # shop
    ("shop", "*", "shop", "{value}"),
    # tourism
    ("tourism", "*", "tourism", "{value}"),
    # leisure
    ("leisure", "*", "leisure", "{value}"),
    # office
    ("office", "*", "office", "{value}"),
    # historic
    ("historic", "*", "historic", "{value}"),
    # public_transport
    ("public_transport", "*", "public_transport", "{value}"),
]

# ---- Phase 2: Notable buildings --------------------------------------------
BUILDING_VALUES = {
    "commercial", "retail", "hospital", "school", "university",
    "civic", "public", "office", "mosque", "church", "synagogue",
    "temple", "monastery",
}

# ---- Phase 3: Expanded categories (used if < 100k) --------------------------
EXPANDED_BUILDING_VALUES = BUILDING_VALUES | {
    "apartments", "hotel", "residential", "yes",
}

# Additional tag pairs for expansion
EXPANDED_TAGS: list[tuple[str, str, str, str]] = [
    ("aeroway", "terminal", "aeroway", "terminal"),
    ("highway", "bus_stop", "highway", "bus_stop"),
    ("place", "neighbourhood", "place", "neighbourhood"),
    ("landuse", "residential", "landuse", "residential"),
    ("landuse", "commercial", "landuse", "commercial"),
    ("landuse", "retail", "landuse", "retail"),
    ("landuse", "industrial", "landuse", "industrial"),
    ("landuse", "military", "landuse", "military"),
    ("natural", "wood", "natural", "wood"),
    ("natural", "water", "natural", "water"),
    ("leisure", "park", "leisure", "park"),
    ("leisure", "pitch", "leisure", "pitch"),
    ("leisure", "track", "leisure", "track"),
    ("leisure", "swimming_pool", "leisure", "swimming_pool"),
    ("sport", "*", "sport", "{value}"),
    ("railway", "station", "railway", "station"),
    ("railway", "halt", "railway", "halt"),
    ("railway", "tram_stop", "railway", "tram_stop"),
    ("power", "tower", "power", "tower"),
    ("power", "substation", "power", "substation"),
    ("man_made", "*", "man_made", "{value}"),
    ("emergency", "*", "emergency", "{value}"),
    ("healthcare", "*", "healthcare", "{value}"),
]

BUS_STOP_CAP = 50_000  # cap bus stops unless we need them to reach 100k
ADDR_NODE_LIMIT = 200_000  # cap addr:housenumber nodes

TARGET_POI = 100_000
BATCH_SIZE = 5000


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------
def download_pbf(url: str, dest: Path, *, chunk_size: int = 65536) -> None:
    """Download PBF with progress display. Re-downloads if file is incomplete."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"[OK] PBF already cached at {dest} ({dest.stat().st_size // 1024 // 1024} MB)")
        return

    print(f"[DOWNLOAD] {url}")
    print(f"[DOWNLOAD] -> {dest}")

    req = urllib.request.Request(url, headers={"User-Agent": "ITS-Traffic-HCM/1.0"})

    def report(block_no: int, block_size: int, total_size: int) -> None:
        downloaded = block_no * block_size
        pct = min(100.0, downloaded / max(total_size, 1) * 100) if total_size > 0 else 0
        bar_len = 40
        filled = int(bar_len * pct / 100)
        bar = "#" * filled + "-" * (bar_len - filled)
        sys.stdout.write(f"\r[{bar}] {pct:.1f}%  {downloaded // 1024 // 1024} MB")
        sys.stdout.flush()

    with urllib.request.urlopen(req, timeout=300) as response:
        total_size = int(response.headers.get("Content-Length", 0))
        with open(dest, "wb") as f_out:
            block_no = 0
            while True:
                block = response.read(chunk_size)
                if not block:
                    break
                f_out.write(block)
                block_no += 1
                report(block_no, chunk_size, total_size)

    print()
    print(f"[OK] Downloaded {dest.stat().st_size // 1024 // 1024} MB")


# ---------------------------------------------------------------------------
# Pyrosm processing
# ---------------------------------------------------------------------------
def _get_pyrosm_conf() -> dict:
    """Return a pyrosm configuration dict pointing at the PBF."""
    return {"location": str(PBF_PATH)}


def extract_pois_pyrosm() -> list[dict]:
    """
    Read the PBF with pyrosm and return a list of POI record dicts.
    Handles nodes, ways, and relation members that act as POIs.
    """
    try:
        from pyrosm import OSM
    except ImportError:
        print("[ERROR] pyrosm not installed. Trying osmium fallback...")
        return extract_pois_osmium()

    print("[PYROSM] Reading PBF...")
    t0 = time.time()

    osm = OSM(str(PBF_PATH), bounding_box=HCM_BBOX)

    records: list[dict] = []

    # ---- Get all POI tags we care about (for fast filtering) ---------------
    # We collect POI tags from the OSM data using pyrosm's built-in methods.
    # pyrosm.get_pois() returns nodes + ways + relations with POI tags.

    # Build tag filter for pyrosm
    # pyrosm accepts a dict of {key: [values]} or a list of keys
    poi_keys = [
        "amenity", "shop", "tourism", "leisure", "office",
        "historic", "public_transport", "aeroway",
        "building", "highway", "place", "landuse",
        "natural", "sport", "railway", "power", "man_made",
        "emergency", "healthcare",
    ]

    try:
        pois = osm.get_pois(tags=poi_keys)
        print(f"[PYROSM] get_pois() returned {len(pois)} raw rows in {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"[PYROSM] get_pois() failed: {e}. Trying get_data()...")
        pois = osm.get_data()
        print(f"[PYROSM] get_data() returned {len(pois)} raw rows")

    if pois is None or len(pois) == 0:
        print("[PYROSM] No POIs returned. Trying osmium fallback.")
        return extract_pois_osmium()

    # Convert to list of dicts
    pois = pois.reset_index() if hasattr(pois, "reset_index") else pois

    for _, row in pois.iterrows():
        try:
            tags = dict(row) if not isinstance(row, dict) else row
            lat = tags.pop("lat", None)
            lon = tags.pop("lon", None)
            osm_type = str(tags.pop("osm_type", "node")).lower()
            osm_id = int(tags.pop("id", 0))

            # Determine category and subcategory
            category, subcategory = _classify_tags(tags)
            if category is None:
                continue

            name = (
                tags.get("name")
                or tags.get("name:vi")
                or tags.get("name:en")
                or ""
            )
            if not name or len(name.strip()) < 1:
                continue

            # Filter building by value if needed
            if category == "building":
                val = tags.get("building", "yes")
                if val == "yes":
                    # check if it's notable
                    pass
                elif val not in BUILDING_VALUES:
                    # skip unless we need more
                    continue

            # Filter highway=bus_stop
            if category == "highway" and subcategory == "bus_stop":
                # keep all for now, cap later
                pass

            address = _build_address(tags)

            record = {
                "osm_type": osm_type,
                "osm_id": osm_id,
                "name": name.strip(),
                "lat": lat,
                "lon": lon,
                "category": category,
                "subcategory": subcategory,
                "district": None,
                "address": address,
                "tags": tags,
            }
            if record["lat"] is not None and record["lon"] is not None:
                records.append(record)
        except Exception:
            continue

    print(f"[PYROSM] Extracted {len(records)} named POIs in {time.time()-t0:.1f}s")
    return records


def extract_pois_osmium() -> list[dict]:
    """
    Fallback: use osmium-tool command line to extract POIs.
    osmium tags-filter must be installed.
    """
    print("[OSMIUM] Using osmium command-line fallback...")
    import subprocess

    records: list[dict] = []

    # Try to use osmium to export nodes with POI tags
    # We'll use a python-based approach with osmium if available
    try:
        result = subprocess.run(
            ["osmium", "--version"], capture_output=True, text=True
        )
        print(f"[OSMIUM] version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("[ERROR] osmium-tool not found. Cannot process PBF.")
        return []

    # For now, return empty - pyrosm is the preferred path
    return []


def _classify_tags(tags: dict) -> tuple[str | None, str | None]:
    """Return (category, subcategory) from a tag dict."""
    # Priority order
    for key in [
        "amenity", "shop", "tourism", "leisure", "office",
        "historic", "public_transport", "aeroway",
        "building", "highway", "place", "landuse",
        "natural", "sport", "railway", "power",
        "man_made", "emergency", "healthcare",
    ]:
        if key in tags:
            val = tags[key]
            return key, str(val) if val else ""
    return None, None


def _build_address(tags: dict) -> str:
    """Build a single-line address string from OSM addr:* tags."""
    parts = []
    for key, label in [
        ("addr:housenumber", "số"),
        ("addr:street", "đường"),
        ("addr:city", "thành phố"),
        ("addr:district", "quận"),
        ("addr:ward", "phường"),
    ]:
        v = tags.get(key, "").strip()
        if v:
            parts.append(v)
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Expansion helpers
# ---------------------------------------------------------------------------
def expand_to_target(
    records: list[dict], total_before: int
) -> list[dict]:
    """
    If records < TARGET_POI, add more POI categories until we reach the target.
    Returns the expanded list.
    """
    if len(records) >= TARGET_POI:
        print(f"[EXPAND] Already have {len(records):,} records >= target {TARGET_POI:,}")
        return records

    # Cap highway=bus_stop if present
    bus_stops = [r for r in records if r["category"] == "highway" and r["subcategory"] == "bus_stop"]
    non_bus = [r for r in records if not (r["category"] == "highway" and r["subcategory"] == "bus_stop")]

    if len(bus_stops) > BUS_STOP_CAP:
        random.seed(42)
        bus_stops = random.sample(bus_stops, BUS_STOP_CAP)
        print(f"[EXPAND] Capped bus stops to {BUS_STOP_CAP:,}")

    records = non_bus + bus_stops
    print(f"[EXPAND] After bus_stop cap: {len(records):,} records")

    if len(records) >= TARGET_POI:
        return records

    # Try loading addr:housenumber nodes via pyrosm
    extra = _load_addr_nodes()
    if extra:
        records.extend(extra)
        print(f"[EXPAND] Added {len(extra):,} addr:housenumber nodes: {len(records):,} total")

    if len(records) >= TARGET_POI:
        return records

    # Load expanded building types
    extra = _load_expanded_buildings()
    if extra:
        records.extend(extra)
        print(f"[EXPAND] Added {len(extra):,} expanded buildings: {len(records):,} total")

    return records


def _load_addr_nodes() -> list[dict]:
    """Load addr:housenumber nodes with names (approximate addresses)."""
    try:
        from pyrosm import OSM
    except ImportError:
        return []

    try:
        osm = OSM(str(PBF_PATH), bounding_box=HCM_BBOX)
        nodes = osm.get_node()
        if nodes is None:
            return []
        nodes = nodes.reset_index() if hasattr(nodes, "reset_index") else nodes
    except Exception as e:
        print(f"[ADDR] Failed to get nodes: {e}")
        return []

    records = []
    count = 0
    for _, row in nodes.iterrows():
        if count >= ADDR_NODE_LIMIT:
            break
        try:
            tags = dict(row) if not isinstance(row, dict) else row
            lat = tags.pop("lat", None)
            lon = tags.pop("lon", None)
            if lat is None or lon is None:
                continue
            tags.pop("osm_type", None)
            tags.pop("id", None)

            name = (
                tags.get("name")
                or tags.get("name:vi")
                or tags.get("addr:housenumber", "")
            ).strip()
            if not name:
                continue

            category = "address"
            subcategory = tags.get("addr:street", "unknown") or "unknown"
            address = _build_address(tags)

            records.append({
                "osm_type": "node",
                "osm_id": int(tags.get("id", 0)),
                "name": name,
                "lat": lat,
                "lon": lon,
                "category": category,
                "subcategory": subcategory,
                "district": None,
                "address": address,
                "tags": tags,
            })
            count += 1
        except Exception:
            continue

    print(f"[ADDR] Loaded {len(records):,} address nodes")
    return records


def _load_expanded_buildings() -> list[dict]:
    """Load buildings with expanded value set."""
    try:
        from pyrosm import OSM
    except ImportError:
        return []

    try:
        osm = OSM(str(PBF_PATH), bounding_box=HCM_BBOX)
        buildings = osm.get_buildings()
        if buildings is None:
            return []
        buildings = buildings.reset_index() if hasattr(buildings, "reset_index") else buildings
    except Exception as e:
        print(f"[BUILDINGS] Failed: {e}")
        return []

    records = []
    count = 0
    for _, row in buildings.iterrows():
        if count >= 50_000:
            break
        try:
            tags = dict(row) if not isinstance(row, dict) else row
            lat = tags.pop("lat", None)
            lon = tags.pop("lon", None)
            tags.pop("osm_type", None)
            tags.pop("id", None)

            name = (
                tags.get("name")
                or tags.get("name:vi")
                or tags.get("building", "")
            ).strip()
            if not name:
                continue

            val = tags.get("building", "yes")
            if val == "yes":
                val = "other"

            records.append({
                "osm_type": "way",
                "osm_id": int(tags.get("id", 0)),
                "name": name,
                "lat": lat,
                "lon": lon,
                "category": "building",
                "subcategory": val,
                "district": None,
                "address": _build_address(tags),
                "tags": tags,
            })
            count += 1
        except Exception:
            continue

    print(f"[BUILDINGS] Loaded {len(records):,} expanded buildings")
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    t_start = time.time()
    print("=" * 60)
    print("HCM POI ETL  |  target: 100,000+ POIs")
    print("=" * 60)

    # 1. Download PBF
    download_pbf(PBF_URL, PBF_PATH)

    if not PBF_PATH.exists():
        print("[FATAL] PBF not found. Aborting.")
        sys.exit(1)

    # 2. Install pyrosm if needed
    try:
        import pyrosm
        print(f"[OK] pyrosm {pyrosm.__version__} already installed")
    except ImportError:
        print("[INSTALL] Installing pyrosm...")
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyrosm", "-q"],
            check=True,
        )
        print("[OK] pyrosm installed")

    # 3. Extract POIs
    raw_records = extract_pois_pyrosm()

    if not raw_records:
        print("[FATAL] No POIs extracted. Aborting.")
        sys.exit(1)

    print(f"[STATS] Raw extracted: {len(raw_records):,}")

    # 4. Expand to 100k if needed
    records = expand_to_target(raw_records, len(raw_records))
    print(f"[STATS] After expansion: {len(records):,}")

    # 5. Remove duplicates in memory (osm_type, osm_id)
    seen: set[tuple] = set()
    unique_records = []
    for r in records:
        key = (r["osm_type"], r["osm_id"])
        if key not in seen:
            seen.add(key)
            unique_records.append(r)
    print(f"[STATS] After dedup: {len(unique_records):,}")

    # 6. Load into SQLite
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "streamlit_app"))
    from lib.poi_db import POIDatabase

    db = POIDatabase(DB_PATH)
    db.init_db()
    print(f"[DB] Initialized at {DB_PATH}")

    # Clear existing data for fresh load
    db._ensure_conn().execute("DELETE FROM pois;")
    db._ensure_conn().commit()
    print("[DB] Cleared existing pois table")

    inserted = 0
    for i in range(0, len(unique_records), BATCH_SIZE):
        batch = unique_records[i : i + BATCH_SIZE]
        n = db.bulk_insert(batch)
        inserted += n
        elapsed = time.time() - t_start
        rate = inserted / max(elapsed, 0.1)
        print(
            f"  batch {i//BATCH_SIZE+1:>3}: +{n:>6} inserted "
            f"(total {inserted:,}) | {rate:,.0f} rec/s"
        )

    print(f"[DB] Total inserted: {inserted:,}")

    # 7. Rebuild FTS
    print("[FTS] Rebuilding FTS5 index...")
    t_fts = time.time()
    db.rebuild_fts()
    print(f"[FTS] Rebuild done in {time.time()-t_fts:.1f}s")

    # 8. Summary
    elapsed_total = time.time() - t_start
    total_count = db.count()

    print()
    print("=" * 60)
    print("ETL SUMMARY")
    print("=" * 60)
    print(f"  Total POIs     : {total_count:,}")
    print(f"  Target         : {TARGET_POI:,}")
    print(f"  Status         : {'ACHIEVED' if total_count >= TARGET_POI else 'BELOW TARGET'}")
    print(f"  Elapsed        : {elapsed_total:.1f}s")

    print()
    print("Top 20 categories:")
    for cat, cnt in db.top_categories(20):
        print(f"  {cat:<25} {cnt:>10,}")

    print()
    print(f"DB file: {DB_PATH}")
    print(f"DB size: {DB_PATH.stat().st_size // 1024 // 1024} MB")

    db.close()


if __name__ == "__main__":
    main()
