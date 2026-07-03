import json
from collections import Counter

with open("c:/Users/Admin/Downloads/ITS/TRAFFIC_PROCESSING/data/osm_hcmc_raw.json", encoding="utf-8") as f:
    d = json.load(f)

els = d.get("elements", [])
ways = [e for e in els if e.get("type") == "way"]
unknown = [e for e in ways if e.get("tags", {}).get("highway") in (None, "unknown")]

print(f"Unknown highways: {len(unknown)}")
print("\nSample unknown ways (first 5 with names):")
named = [(e, e.get("tags", {}).get("name", "")) for e in unknown if e.get("tags", {}).get("name")]
for way, name in named[:10]:
    tags = way.get("tags", {})
    print(f"  {name}: highway={tags.get('highway')}, lanes={tags.get('lanes')}, surface={tags.get('surface')}, maxspeed={tags.get('maxspeed')}")

# Check what tags unknown ways have
tag_keys = Counter()
for e in unknown:
    for k in e.get("tags", {}).keys():
        tag_keys[k] += 1
print("\nTag keys in unknown highways:", dict(tag_keys.most_common(20)))

# Check if all ways have names
named_unknown = [e for e in unknown if e.get("tags", {}).get("name")]
unnamed = [e for e in unknown if not e.get("tags", {}).get("name")]
print(f"\nUnknown with names: {len(named_unknown)}, without names: {len(unnamed)}")

# Check node lat/lon coverage
nodes = [e for e in els if e.get("type") == "node"]
print(f"\nNodes: {len(nodes)}")
print(f"Nodes with tags: {sum(1 for n in nodes if n.get('tags'))}")
# Check lat/lon range
lats = [n["lat"] for n in nodes]
lons = [n["lon"] for n in nodes]
print(f"Lat range: {min(lats):.4f} - {max(lats):.4f}")
print(f"Lon range: {min(lons):.4f} - {max(lons):.4f}")
# HCMC approx: 10.7-10.9 lat, 106.6-106.85 lon
in_hcmc = sum(1 for n in nodes if 10.7 <= n["lat"] <= 10.95 and 106.55 <= n["lon"] <= 106.9)
print(f"Nodes in HCMC bounding box: {in_hcmc}")
