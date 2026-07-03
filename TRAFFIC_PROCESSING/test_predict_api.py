import requests, json

tests = [
    ("LOW  len=500,  vc=0.1,  rush=false, hour=2",
     {"length": 500, "max_velocity": 30, "vc_ratio": 0.1, "hour": 2, "is_weekend": False, "is_rush": False}),
    ("HIGH len=4900, vc=1.4,  rush=true,  hour=17",
     {"length": 4900, "max_velocity": 110, "vc_ratio": 1.4, "hour": 17, "is_weekend": False, "is_rush": True}),
    ("MID  len=2000, vc=0.5,  rush=false, hour=12",
     {"length": 2000, "max_velocity": 60, "vc_ratio": 0.5, "hour": 12, "is_weekend": False, "is_rush": False}),
    ("WKND len=2000, vc=0.8,  rush=true,  hour=9",
     {"length": 2000, "max_velocity": 80, "vc_ratio": 0.8, "hour": 9, "is_weekend": True, "is_rush": True}),
]

for label, payload in tests:
    r = requests.post("http://127.0.0.1:8000/api/predict", json=payload)
    d = r.json()
    print(f"{label}")
    print(f"  -> prediction={d['prediction']}, confidence={d['confidence']:.4f}")
    probs = ", ".join(f"{p['letter']}={p['value']:.4f}" for p in d["probability"])
    print(f"  probs: {probs}")
    print()
