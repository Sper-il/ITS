"""
Train a fast LOS predictor that uses only UI-available features.
Saves: los_engine_model.pkl  (joblib dump)
       los_engine.py           (loader + predict_ui function)
"""
import sys, warnings, math, joblib, json
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder

DATA  = Path(r"C:\Users\Admin\Downloads\ITS\TRAFFIC_PROCESSING\scripts\outputs\train_features.csv")
MODEL_OUT = Path(r"C:\Users\Admin\Downloads\ITS\TRAFFIC_PROCESSING\models\los_engine_model.pkl")
ENGINE_OUT = Path(r"C:\Users\Admin\Downloads\ITS\TRAFFIC_PROCESSING\webapp\backend\core\los_engine.py")

# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading training data...")
df = pd.read_csv(DATA, low_memory=False)
df = df.dropna(subset=["LOS", "length", "max_velocity", "vc_ratio",
                        "period_hour", "is_weekend", "is_rush_hour"])
print(f"  {len(df)} rows, columns: {df.shape[1]}")

# ── Feature engineering ──────────────────────────────────────────────────────
FEATURE_KEYS = [
    "length", "max_velocity", "vc_ratio", "period_hour",
    "is_weekend", "is_rush_hour",
    "hour_sin", "hour_cos",
    "is_morning_rush", "is_evening_rush", "is_night", "is_working_hours", "is_lunch",
    "length_norm", "max_velocity_norm",
    "vc_x_hour", "length_x_vc", "weekend_x_rush",
    "delay_proxy", "capacity_util",
]

def make_row(length, max_velocity, vc_ratio, hour, is_weekend, is_rush):
    return {
        "length":             length,
        "max_velocity":       max_velocity,
        "vc_ratio":           vc_ratio,
        "period_hour":        int(hour),
        "is_weekend":         int(bool(is_weekend)),
        "is_rush_hour":       int(bool(is_rush)),
        "hour_sin":           math.sin(2 * math.pi * hour / 24),
        "hour_cos":           math.cos(2 * math.pi * hour / 24),
        "is_morning_rush":    int(7 <= hour <= 9),
        "is_evening_rush":    int(16 <= hour <= 19),
        "is_night":           int(hour >= 22 or hour <= 5),
        "is_working_hours":   int(8 <= hour <= 17 and not is_weekend),
        "is_lunch":           int(11 <= hour <= 13),
        "length_norm":         length / 5000.0,
        "max_velocity_norm":   max_velocity / 120.0,
        "vc_x_hour":           vc_ratio * hour,
        "length_x_vc":         length * vc_ratio,
        "weekend_x_rush":      int(is_weekend and is_rush),
        "delay_proxy":         vc_ratio * (2.0 if is_rush else 1.0),
        "capacity_util":       min(vc_ratio / 1.0, 1.5) if max_velocity > 0 else 0,
    }

def build_X(df_rows):
    rows = []
    for _, r in df_rows.iterrows():
        row = make_row(r["length"], r["max_velocity"], r["vc_ratio"],
                       r["period_hour"], r["is_weekend"], r["is_rush_hour"])
        rows.append(row)
    return pd.DataFrame(rows)

print("Building feature matrix...")
X = build_X(df)
le = LabelEncoder()
y = le.fit_transform(df["LOS"])
print(f"  X shape: {X.shape}, classes: {list(le.classes_)}")

# ── Train ────────────────────────────────────────────────────────────────────
print("\nTraining Random Forest...")
rf = RandomForestClassifier(
    n_estimators=300, max_depth=18, min_samples_leaf=4,
    class_weight="balanced", random_state=42, n_jobs=-1
)
rf_scores = cross_val_score(rf, X, y, cv=5, scoring="accuracy")
print(f"  RF CV: {rf_scores.mean():.3f} ± {rf_scores.std():.3f}")

print("\nTraining Gradient Boosting...")
gb = GradientBoostingClassifier(
    n_estimators=200, max_depth=6, learning_rate=0.1,
    subsample=0.8, random_state=42
)
gb_scores = cross_val_score(gb, X, y, cv=5, scoring="accuracy")
print(f"  GB CV: {gb_scores.mean():.3f} ± {gb_scores.std():.3f}")

# Pick best
if rf_scores.mean() >= gb_scores.mean():
    best, best_name, best_score = rf, "RandomForest", rf_scores.mean()
else:
    best, best_name, best_score = gb, "GradientBoosting", gb_scores.mean()
print(f"\nBest model: {best_name} (CV={best_score:.3f})")

# Fit on full data
best.fit(X, y)

# Feature importance
print("\nTop 10 feature importances:")
imp = sorted(zip(FEATURE_KEYS, best.feature_importances_), key=lambda x: -x[1])
for f, i in imp[:10]:
    print(f"  {f}: {i:.4f}")

# ── Save model ───────────────────────────────────────────────────────────────
MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
joblib.dump({"model": best, "le": le, "feature_keys": FEATURE_KEYS}, MODEL_OUT)
print(f"\nSaved model to {MODEL_OUT}")

# ── Test ─────────────────────────────────────────────────────────────────────
print("\n--- Prediction tests ---")
def test_ui(length, max_velocity, vc_ratio, hour, is_weekend, is_rush):
    row = pd.DataFrame([make_row(length, max_velocity, vc_ratio, hour, is_weekend, is_rush)])
    pred_idx = int(best.predict(row)[0])
    probs = best.predict_proba(row)[0]
    pred = le.inverse_transform([pred_idx])[0]
    conf = float(probs[pred_idx])
    proba_dict = dict(zip(le.classes_, [float(p) for p in probs]))
    return pred, conf, proba_dict

tests = [
    ("Free flow",        50,  120, 0.05,  3, False, False),
    ("Light traffic",   500,   80,  0.3,  10, False, False),
    ("Moderate",       1000,   60,  0.6,  12, False, False),
    ("Heavy",          2000,   40,  0.9,  17, False, True),
    ("Near saturation", 3000,  30,  1.2,  18, False, True),
    ("Gridlock",       5000,   20,  1.5,  18, False, True),
    ("Morning rush",   2000,   50,  1.0,   8, False, True),
    ("Night clear",    1000,   80,  0.2,  23, False, False),
    ("Weekend leisure", 500,   60,  0.4,  14, True,  False),
]

for desc, *args in tests:
    pred, conf, proba = test_ui(*args)
    top3 = sorted(proba.items(), key=lambda x: -x[1])[:3]
    print(f"  {desc:20s}: LOS={pred} (conf={conf:.3f}) | " +
          ", ".join(f"{k}={v:.3f}" for k, v in top3))

# Check different predictions
unique_preds = set()
for desc, *args in tests:
    pred, _, _ = test_ui(*args)
    unique_preds.add(pred)
print(f"\nUnique predictions across tests: {unique_preds}")

# ── Write los_engine.py ───────────────────────────────────────────────────────
ENGINE_OUT.parent.mkdir(parents=True, exist_ok=True)
with open(ENGINE_OUT, "w", encoding="utf-8") as fh:
    fh.write(f'''"""los_engine.py — Fast LOS predictor using only UI-available features.
Trained on {len(df)} rows using {best_name} (CV accuracy: {best_score:.3f}).

Usage:
    from backend.core.los_engine import predict_ui
    label, confidence, proba_dict = predict_ui(length=1000, max_velocity=60,
                                              vc_ratio=0.6, hour=12,
                                              is_weekend=False, is_rush=False)
"""
from __future__ import annotations
import math
import joblib
from pathlib import Path

_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "los_engine_model.pkl"

_cached: dict | None = None

def _load():
    global _cached
    if _cached is None:
        _cached = joblib.load(_MODEL_PATH)
    return _cached

FEATURE_KEYS = {FEATURE_KEYS!r}

def predict_ui(
    length: float,
    max_velocity: float,
    vc_ratio: float,
    hour: int,
    is_weekend: bool,
    is_rush: bool,
):
    """Predict LOS. Returns (label, confidence, proba_dict)."""
    data = _load()
    model = data["model"]
    le = data["le"]

    row = {{
        "length":             length,
        "max_velocity":       max_velocity,
        "vc_ratio":           vc_ratio,
        "period_hour":        int(hour),
        "is_weekend":         int(bool(is_weekend)),
        "is_rush_hour":       int(bool(is_rush)),
        "hour_sin":           math.sin(2 * math.pi * hour / 24),
        "hour_cos":           math.cos(2 * math.pi * hour / 24),
        "is_morning_rush":    int(7 <= hour <= 9),
        "is_evening_rush":    int(16 <= hour <= 19),
        "is_night":           int(hour >= 22 or hour <= 5),
        "is_working_hours":   int(8 <= hour <= 17 and not is_weekend),
        "is_lunch":           int(11 <= hour <= 13),
        "length_norm":         length / 5000.0,
        "max_velocity_norm":   max_velocity / 120.0,
        "vc_x_hour":           vc_ratio * hour,
        "length_x_vc":         length * vc_ratio,
        "weekend_x_rush":      int(is_weekend and is_rush),
        "delay_proxy":         vc_ratio * (2.0 if is_rush else 1.0),
        "capacity_util":       (min(vc_ratio / 1.0, 1.5) if max_velocity > 0 else 0),
    }}

    import pandas as pd
    X = pd.DataFrame([row])
    pred_idx = int(model.predict(X)[0])
    probs = model.predict_proba(X)[0]
    pred = le.inverse_transform([pred_idx])[0]
    conf = float(probs[pred_idx])
    proba_dict = dict(zip(le.classes_, [float(p) for p in probs]))
    return pred, conf, proba_dict
''')

print(f"\nWrote {ENGINE_OUT}")
print("DONE! Run `python app.py` to test in browser.")
