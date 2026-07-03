"""Seed the locations SQLite DB from presets.py and optionally from an OSM CSV."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_app.data.presets import HCM_PRESETS
from streamlit_app.data.locations_db import (
    init_db,
    seed_from_presets,
    add_many_locations,
    get_location_count,
)

# Points to the cleaned CSV (osm_hcmc_locations_cleaned.csv).
# To re-generate: run python clean_csv.py from the TRAFFIC_PROCESSING directory.
_OSM_CSV = Path(__file__).parent.parent / "data" / "osm_hcmc_locations_cleaned.csv"


def main() -> None:
    print("Initializing DB schema...")
    init_db()

    # Seed from presets
    count = seed_from_presets(HCM_PRESETS)
    print(f"Seeded {count} locations from presets.py")

    # Seed from OSM CSV if present
    osm_count = 0
    if _OSM_CSV.exists():
        rows = []
        with open(_OSM_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        if rows:
            osm_count = add_many_locations(rows)
            print(f"Seeded {osm_count} locations from OSM CSV")

    total = get_location_count()
    print(f"Total locations in DB: {total}")


if __name__ == "__main__":
    main()
