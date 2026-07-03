"""Test the exact same payloads the browser sends."""
import requests, json, time

# Simulate what Playwright does: initial load + rapid slider changes
base = "http://127.0.0.1:8000"

# Test: what happens when sliders are at specific values
# The browser sets slider-value via JS dispatch_event
# slider-vc: 0-150 range, value=85 -> vc_ratio = 85/100 = 0.85
# slider-length: 50-5000 range, value=1240 -> length = 1240
# slider-speed: 20-120 range, value=60 -> max_velocity = 60
# slider-hour: 0-23 range, value=18 -> hour = 18

tests = [
    ("Initial defaults", {"length": 1240, "max_velocity": 60, "vc_ratio": 0.85, "hour": 18, "is_weekend": False, "is_rush": True}),
    ("After slider change (50%)", {"length": 2550, "max_velocity": 70, "vc_ratio": 0.75, "hour": 11, "is_weekend": False, "is_rush": False}),
    ("Rush hour", {"length": 2000, "max_velocity": 50, "vc_ratio": 1.0, "hour": 17, "is_weekend": False, "is_rush": True}),
    ("Weekend", {"length": 1000, "max_velocity": 60, "vc_ratio": 0.6, "hour": 14, "is_weekend": True, "is_rush": False}),
    # Rapid-fire (like the browser does)
    ("Rapid 1", {"length": 500, "max_velocity": 30, "vc_ratio": 0.1, "hour": 2, "is_weekend": False, "is_rush": False}),
    ("Rapid 2", {"length": 4900, "max_velocity": 110, "vc_ratio": 1.4, "hour": 17, "is_weekend": False, "is_rush": True}),
    ("Rapid 3", {"length": 2550, "max_velocity": 70, "vc_ratio": 0.75, "hour": 11, "is_weekend": False, "is_rush": False}),
]

session = requests.Session()

for name, payload in tests:
    try:
        r = session.post(f"{base}/api/predict", json=payload, timeout=5)
        if r.status_code != 200:
            print(f"FAIL {name}: HTTP {r.status_code}")
            print(f"  Body: {r.text[:300]}")
        else:
            d = r.json()
            print(f"OK   {name}: {d['prediction']} (conf={d['confidence']:.3f})")
    except Exception as ex:
        print(f"ERROR {name}: {ex}")
    time.sleep(0.05)  # small delay

print("\nDone!")
