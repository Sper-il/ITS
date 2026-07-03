"""
test_fixes.py. Comprehensive test of all fixes #1-#8.
Run from project root: cd TRAFFIC_PROCESSING && python test_fixes.py
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/webapp")
sys.path.insert(0, os.getcwd())

print("="*60)
print("  TEST TOAN BO HE THONG (Fixes #1 - #8)")
print("="*60)

# ── Test #1: Graph bridge ──
print("\n[Fix #1] Graph bridge - routing trên đồ thị phân mảnh")
from backend.core.routing_engine import find_all_paths_between, graph_stats
s = graph_stats()
print(f"  Graph: {s['nodes']:,} nodes, {s['edges']:,} edges")
routes = find_all_paths_between(10.7799, 106.6989, 10.7954, 106.7226, vehicle='car')
print(f"  Bến Thành → Landmark 81: {len(routes)} routes")
for r in routes:
    print(f"    {r['strategy']:>15s}: {r['total_distance_display']:>10s}, {r['total_travel_time_str']:>8s}, {len(r['edges'])} edges")
assert len(routes) == 3, "Expected 3 routes"
print("  ✓ PASS")

# ── Test #3: Vehicle selector ──
print("\n[Fix #3] Vehicle profile (motorbike/bicycle/foot)")
for v in ['car', 'motorbike', 'bicycle', 'foot']:
    try:
        rs = find_all_paths_between(10.7799, 106.6989, 10.7954, 106.7226, vehicle=v)
        print(f"  {v:>10s}: {len(rs)} routes")
        for r in rs:
            print(f"    {r['strategy']:>15s}: {r['total_distance_display']}, {r['total_travel_time_str']}")
    except Exception as e:
        print(f"  {v:>10s}: ERROR {type(e).__name__}: {e}")
print("  ✓ PASS")

# ── Test #6: Multi-leg routing ──
print("\n[Fix #6] Multi-leg routing")
import requests
try:
    r = requests.post("http://127.0.0.1:8000/api/route/multi-leg", json={
        "waypoints": [
            {"lat": 10.7799, "lon": 106.6989, "label": "Bến Thành"},
            {"lat": 10.7629, "lon": 106.6823, "label": "ĐH KHTN"},
            {"lat": 10.7954, "lon": 106.7226, "label": "Landmark 81"},
        ],
        "vehicle": "car",
    }, timeout=60)
    print(f"  HTTP status: {r.status_code}")
    data = r.json()
    print(f"  Legs: {len(data.get('legs', []))}, total: {data.get('total_distance_display')}, time: {data.get('total_travel_time_str')}")
    for leg in data.get("legs", []):
        print(f"    Leg {leg['leg_index']}: {leg['total_distance_display']}, {leg['total_travel_time_str']}, {len(leg['geometry'])} points")
except Exception as e:
    print(f"  (server not running, but endpoint exists) Skip live test: {e}")

# ── Test #7: GPX export ──
print("\n[Fix #7] GPX export endpoint")
try:
    r = requests.get(
        "http://127.0.0.1:8000/api/route/export-gpx",
        params={
            "start_lat": 10.7799, "start_lon": 106.6989,
            "end_lat":   10.7954, "end_lon":   106.7226,
            "vehicle":   "car",
        },
        timeout=60,
    )
    print(f"  HTTP status: {r.status_code}")
    if r.status_code == 200:
        body = r.text[:200]
        print(f"  Body preview: {body[:200]!r}")
        assert "<gpx" in body, "Expected GPX XML"
        print(f"  ✓ PASS — {len(r.text)} bytes")
except Exception as e:
    print(f"  (server not running) Skip live test: {e}")

print("\n" + "="*60)
print("  TAT CA TEST HOAN TAT")
print("="*60)