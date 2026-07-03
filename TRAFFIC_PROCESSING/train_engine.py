"""LOS trainer with road_type feature for better prediction."""
import sys, warnings, math, joblib
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.preprocessing import LabelEncoder

DATA = Path(r"C:\Users\Admin\Downloads\ITS\TRAFFIC_PROCESSING\scripts\outputs\train_features.csv")
MODEL_OUT = Path(r"C:\Users\Admin\Downloads\ITS\TRAFFIC_PROCESSING\models\los_engine_model.pkl")

print("Loading data...")
df = pd.read_csv(DATA, low_memory=False)
df = df.dropna(subset=["LOS", "length", "max_velocity", "vc_ratio",
                        "period_hour", "is_weekend", "is_rush_hour", "hist_vel_mean"])
print(f"  {len(df)} rows")

# Road type distribution
df["road_type"] = df["max_velocity"].apply(
    lambda v: 2 if v >= 80 else 1 if v >= 50 else 0
)  # 0=local, 1=urban, 2=highway

print("\nRoad type distribution:")
print(df["road_type"].value_counts())
print("\nLOS by road_type:")
print(df.groupby("road_type")["LOS"].value_counts(normalize=True).unstack().round(3))

FEATURE_KEYS = [
    "length", "max_velocity", "vc_ratio", "period_hour",
    "is_weekend", "is_rush_hour",
    "hour_sin", "hour_cos",
    "is_morning_rush", "is_evening_rush", "is_night",
    "is_working_hours", "is_lunch",
    "length_norm", "max_velocity_norm",
    "vc_x_hour", "length_x_vc", "weekend_x_rush",
    "delay_proxy", "road_type",
    "vc_norm", "length_log",
]

def make_row(length, max_velocity, vc_ratio, hour, is_weekend, is_rush, road_type=1):
    return {
        "length":           length,
        "max_velocity":     max_velocity,
        "vc_ratio":         vc_ratio,
        "period_hour":      int(hour),
        "is_weekend":       int(bool(is_weekend)),
        "is_rush_hour":    int(bool(is_rush)),
        "hour_sin":        math.sin(2 * math.pi * hour / 24),
        "hour_cos":        math.cos(2 * math.pi * hour / 24),
        "is_morning_rush": int(7 <= hour <= 9),
        "is_evening_rush": int(16 <= hour <= 19),
        "is_night":        int(hour >= 22 or hour <= 5),
        "is_working_hours": int(8 <= hour <= 17 and not is_weekend),
        "is_lunch":        int(11 <= hour <= 13),
        "length_norm":      length / 5000.0,
        "max_velocity_norm": max_velocity / 120.0,
        "vc_x_hour":       vc_ratio * hour,
        "length_x_vc":     length * vc_ratio,
        "weekend_x_rush":  int(is_weekend and is_rush),
        "delay_proxy":      vc_ratio * (2.0 if is_rush else 1.0),
        "road_type":       int(road_type),
        "vc_norm":         vc_ratio / max(max_velocity, 1) * 100,
        "length_log":     math.log1p(length),
    }

print("\nBuilding feature matrix...")
rows = [make_row(r["length"], r["max_velocity"], r["vc_ratio"],
                 r["period_hour"], r["is_weekend"], r["is_rush_hour"], int(r["road_type"]))
       for _, r in df.iterrows()]
X = pd.DataFrame(rows)
le = LabelEncoder()
y = le.fit_transform(df["LOS"])
print(f"  X: {X.shape}, classes: {list(le.classes_)}")

print("\nTraining ExtraTrees (n=200, depth=25)...")
et = ExtraTreesClassifier(n_estimators=200, max_depth=25, min_samples_leaf=2,
                           class_weight="balanced", random_state=42, n_jobs=-1)
et.fit(X, y)
print("  Done.")

# Tests
print("\n--- Tests (with road_type=2 for highway, road_type=1 for urban, road_type=0 for local) ---")
def test_ui(length, max_velocity, vc_ratio, hour, is_weekend, is_rush, road_type=1):
    row = pd.DataFrame([make_row(length, max_velocity, vc_ratio, hour, is_weekend, is_rush, road_type)])
    pred_idx = int(et.predict(row)[0])
    probs = et.predict_proba(row)[0]
    pred = le.inverse_transform([pred_idx])[0]
    conf = float(probs[pred_idx])
    proba = dict(zip(le.classes_, [float(p) for p in probs]))
    return pred, conf, proba

# road_type: 2=highway, 1=urban, 0=local
tests = [
    # Highway scenarios
    ("[Hwy] Free flow",    100, 120, 0.15,  3, False, False, 2),
    ("[Hwy] Light",       200, 100, 0.40, 10, False, False, 2),
    ("[Hwy] Dense",       500,  90, 0.70, 17, False, True,  2),
    ("[Hwy] Near sat.",   500,  80, 0.90, 18, False, True,  2),
    ("[Hwy] Over cap.",   500,  80, 1.20, 18, False, True,  2),
    # Urban scenarios
    ("[Urb] Free flow",   200,  60, 0.25, 12, False, False, 1),
    ("[Urb] Moderate",     300,  50, 0.60, 12, False, False, 1),
    ("[Urb] Heavy",       500,  40, 0.90, 17, False, True,  1),
    ("[Urb] Saturation",  800,  40, 1.20, 18, False, True,  1),
    ("[Urb] Gridlock",   1000,  30, 1.50, 18, False, True,  1),
    # Local scenarios
    ("[Loc] Good",        100,  30, 0.30, 14, True,  False, 0),
    ("[Loc] Congested",   200,  30, 0.90, 18, False, True,  0),
]

for desc, *args in tests:
    pred, conf, proba = test_ui(*args)
    top3 = sorted(proba.items(), key=lambda x: -x[1])[:3]
    print(f"  {desc:25s}: {pred} (conf={conf:.3f}) | " +
          ", ".join(f"{k}={v:.3f}" for k, v in top3))

unique = set(test_ui(*args[:7])[0] for args in tests)
print(f"\nUnique predictions: {unique}")

# Feature importance
print("\nTop features:")
for f, i in sorted(zip(FEATURE_KEYS, et.feature_importances_), key=lambda x: -x[1])[:12]:
    print(f"  {f}: {i:.4f}")

# Save
MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
joblib.dump({
    "model": et, "le": le, "feature_keys": FEATURE_KEYS,
    "model_type": "ExtraTreesClassifier",
}, MODEL_OUT)
print(f"\nSaved to {MODEL_OUT}")
print("DONE!")
