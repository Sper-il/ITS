"""Quick test of the API via requests."""
import requests

tests = [
    ("Free flow",    {"length": 500,  "max_velocity": 30,  "vc_ratio": 0.1, "hour": 2,  "is_weekend": False, "is_rush": False}),
    ("Gridlock",    {"length": 4900, "max_velocity": 110, "vc_ratio": 1.4, "hour": 17, "is_weekend": False, "is_rush": True}),
    ("Normal",      {"length": 2000, "max_velocity": 60,  "vc_ratio": 0.5, "hour": 12, "is_weekend": False, "is_rush": False}),
]

for name, payload in tests:
    try:
        r = requests.post("http://127.0.0.1:8000/api/predict", json=payload)
        if r.status_code != 200:
            print(f"FAIL {name}: HTTP {r.status_code}")
            print(f"  {r.text[:200]}")
        else:
            d = r.json()
            print(f"OK   {name}: {d['prediction']} (conf={d['confidence']:.3f})")
    except Exception as ex:
        print(f"FAIL {name}: {ex}")
