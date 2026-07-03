#!/usr/bin/env python3
"""
OSM Scraper for Ho Chi Minh City, Vietnam
Fetches up to 100,000 locations from OpenStreetMap via the Overpass API.
Uses only Python standard library (urllib.request, csv, json).
"""

import json
import csv
import re
import time
import os
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

# Force UTF-8 stdout encoding for Windows compatibility
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Configuration
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_QUERY = """
[out:json][timeout:300];
(
  node["name"]["addr:city"="Ho Chi Minh City"](10.75,106.55,10.95,106.85);
  node["name:vi"]["addr:city"="Ho Chi Minh City"](10.75,106.55,10.95,106.85);
  node["amenity"]["name"](10.75,106.55,10.95,106.85);
  node["shop"]["name"](10.75,106.55,10.95,106.85);
  node["office"]["name"](10.75,106.55,10.95,106.85);
  node["leisure"]["name"](10.75,106.55,10.95,106.85);
  node["tourism"]["name"](10.75,106.55,10.95,106.85);
  node["public_transport"]["name"](10.75,106.55,10.95,106.85);
  node["building"]["name"](10.75,106.55,10.95,106.85);
  node["highway"]["name"](10.75,106.55,10.95,106.85);
  way["name"]["addr:city"="Ho Chi Minh City"](10.75,106.55,10.95,106.85);
  way["amenity"]["name"](10.75,106.55,10.95,106.85);
  way["shop"]["name"](10.75,106.55,10.95,106.85);
  way["office"]["name"](10.75,106.55,10.95,106.85);
  way["leisure"]["name"](10.75,106.55,10.95,106.85);
  way["tourism"]["name"](10.75,106.55,10.95,106.85);
  way["building"]["name"](10.75,106.55,10.95,106.85);
);
out center;
"""
MAX_RETRIES = 3
RETRY_DELAY = 1
PROGRESS_INTERVAL = 500

# Ho Chi Minh City bounding box
BBOX = {"south": 10.75, "north": 10.95, "west": 106.55, "east": 106.85}


def normalize_name(name):
    """Normalize a name: strip whitespace, collapse multiple spaces."""
    if not name:
        return None
    name = name.strip()
    if not name:
        return None
    name = re.sub(r'\s+', ' ', name)
    return name


def get_category(tags):
    """Determine category from OSM tags."""
    if "amenity" in tags and tags["amenity"]:
        return tags["amenity"]
    if "shop" in tags and tags["shop"]:
        return "shop"
    if "office" in tags and tags["office"]:
        return "office"
    if "leisure" in tags and tags["leisure"]:
        return tags["leisure"]
    if "tourism" in tags and tags["tourism"]:
        return tags["tourism"]
    if "public_transport" in tags and tags["public_transport"]:
        return "transport"
    if "building" in tags:
        if "building:levels" in tags and tags["building:levels"]:
            return "building"
    if "highway" in tags and tags["highway"]:
        highway_vals = ["motorway", "trunk", "primary", "secondary", "tertiary"]
        if tags["highway"] in highway_vals:
            return "road"
    return "other"


def build_address(tags):
    """Build short address string from OSM address tags."""
    parts = []
    for key in ["addr:housenumber", "addr:street", "addr:ward", "addr:district", "addr:city"]:
        if key in tags and tags[key]:
            parts.append(tags[key])
    if parts:
        return ", ".join(parts)
    if "near" in tags and tags["near"]:
        return tags["near"]
    return ""


def get_coords(element):
    """Extract lat/lon from element (node or way with center)."""
    if element["type"] == "node":
        return element.get("lat"), element.get("lon")
    elif element["type"] == "way":
        center = element.get("center", {})
        return center.get("lat"), center.get("lon")
    return None, None


def query_overpass(endpoint):
    """Send query to Overpass API with retry logic."""
    data = urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "OSMScraper/1.0 (Ho Chi Minh City Traffic Project)"
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            req = Request(endpoint, data=data, headers=headers)
            with urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result
        except HTTPError as e:
            if e.code in [429, 500, 502, 503]:
                print(f"  HTTP error {e.code} on attempt {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    print(f"  Waiting {RETRY_DELAY}s before retry...")
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"  Max retries reached for {endpoint}")
                    raise
            else:
                raise
        except URLError as e:
            print(f"  URL error on attempt {attempt + 1}/{MAX_RETRIES}: {e.reason}")
            if attempt < MAX_RETRIES - 1:
                print(f"  Waiting {RETRY_DELAY}s before retry...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  Max retries reached for {endpoint}")
                raise
        except Exception as e:
            print(f"  Unexpected error: {e}")
            raise
    
    return None


def fetch_osm_data():
    """Try Overpass endpoints until one succeeds."""
    for endpoint in OVERPASS_ENDPOINTS:
        print(f"Trying Overpass API: {endpoint}")
        try:
            result = query_overpass(endpoint)
            if result:
                print(f"Successfully fetched data from {endpoint}")
                return result
        except Exception as e:
            print(f"Failed to fetch from {endpoint}: {e}")
            continue
    
    raise RuntimeError("All Overpass endpoints failed")


def process_elements(elements):
    """Process OSM elements, deduplicate by normalized name."""
    seen = {}
    total = len(elements)
    
    for idx, element in enumerate(elements):
        if idx > 0 and idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} / {total} elements...")
        
        tags = element.get("tags", {})
        name = tags.get("name")
        normalized = normalize_name(name)
        
        if not normalized:
            continue
        
        lat, lon = get_coords(element)
        if lat is None or lon is None:
            continue
        
        if normalized not in seen:
            seen[normalized] = {
                "name": normalized,
                "lat": lat,
                "lon": lon,
                "category": get_category(tags),
                "address": build_address(tags),
                "osm_id": element.get("id"),
                "osm_type": element.get("type"),
            }
        else:
            existing = seen[normalized]
            if not existing["address"] and build_address(tags):
                existing["address"] = build_address(tags)
    
    return seen


def count_by_category(locations):
    """Count locations by category."""
    counts = {}
    for loc in locations.values():
        cat = loc["category"]
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def print_category_table(counts, total):
    """Print category breakdown table."""
    print("\n" + "=" * 50)
    print("CATEGORY BREAKDOWN")
    print("=" * 50)
    for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
        pct = (count / total) * 100 if total > 0 else 0
        print(f"  {cat:<20} {count:>6} ({pct:>5.1f}%)")
    print("-" * 50)
    print(f"  {'TOTAL':<20} {total:>6}")
    print("=" * 50)


def save_csv(locations, filepath):
    """Save locations to CSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "lat", "lon", "category", "address", "osm_id", "osm_type"])
        writer.writeheader()
        for loc in sorted(locations.values(), key=lambda x: x["name"]):
            writer.writerow(loc)
    print(f"\nSaved {len(locations)} locations to CSV: {filepath}")


def save_json(data, filepath):
    """Save raw JSON response for debugging."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved raw JSON to: {filepath}")


def main():
    print("=" * 60)
    print("OSM Scraper for Ho Chi Minh City, Vietnam")
    print("=" * 60)
    print(f"Bounding box: S={BBOX['south']}, W={BBOX['west']}, N={BBOX['north']}, E={BBOX['east']}")
    print()
    
    # Fetch data from Overpass
    print("Fetching data from Overpass API...")
    raw_data = fetch_osm_data()
    
    elements = raw_data.get("elements", [])
    print(f"\nTotal elements received: {len(elements)}")
    
    # Save raw JSON
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    json_path = os.path.join(base_dir, "data", "osm_hcmc_raw.json")
    save_json(raw_data, json_path)
    
    # Process and deduplicate
    print("\nProcessing and deduplicating elements...")
    locations = process_elements(elements)
    
    # Count and print statistics
    counts = count_by_category(locations)
    total = len(locations)
    print_category_table(counts, total)
    
    # Save CSV
    csv_path = os.path.join(base_dir, "data", "osm_hcmc_locations.csv")
    save_csv(locations, csv_path)
    
    print("\n" + "=" * 60)
    print(f"SCRAPING COMPLETE")
    print(f"Total unique locations: {total}")
    print("=" * 60)
    
    return total


if __name__ == "__main__":
    main()
