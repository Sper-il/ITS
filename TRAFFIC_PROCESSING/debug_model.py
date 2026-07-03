"""
Debug: trace exactly what the model sees and returns.
"""
import sys, json, math
sys.path.insert(0, "webapp/backend")

from core.model import load_model, _feature_default_template, align_features
import pandas as pd
import numpy as np

ppl, le, feature_names = load_model()

tmpl = _feature_default_template()

def test_row(label, length, max_vel, vc, hour, is_wknd, is_rush):
    row = dict(tmpl)
    overrides = {
        "length": length,
        "max_velocity": max_vel,
        "vc_ratio": vc,
        "period_hour": int(hour),
        "is_weekend": int(bool(is_wknd)),
        "is_rush_hour": int(bool(is_rush)),
        "hour_sin": math.sin(2 * math.pi * hour / 24),
        "hour_cos": math.cos(2 * math.pi * hour / 24),
        "is_morning_rush": int(7 <= hour <= 9),
        "is_evening_rush": int(16 <= hour <= 19),
        "is_night": int(hour >= 22 or hour <= 5),
        "is_working_hours": int(8 <= hour <= 17 and not is_wknd),
        "is_lunch": int(11 <= hour <= 13),
        "length_norm": length / 5000.0,
        "max_velocity_norm": max_vel / 120.0,
        "period_minutes_of_day": hour * 60,
        "period_minute": 0,
        "period_hour_norm": hour / 23.0,
        "period_minutes_of_day_norm": (hour * 60) / 1439.0,
        "vc_x_hour": vc * hour,
        "vc_x_weekday": vc * (5 if is_wknd else 2),
        "length_x_vc": length * vc,
        "weekend_x_rush": int(is_wknd and is_rush),
    }
    for k, v in overrides.items():
        if k in row:
            row[k] = v

    df_in = pd.DataFrame([row])
    df_aligned = align_features(df_in, feature_names)

    nan_cols = df_aligned.isnull().sum()
    nan_cols = nan_cols[nan_cols > 0]
    if len(nan_cols) > 0:
        print(f"  NaN columns: {dict(nan_cols)}")

    # Check key values
    for k in ["length", "max_velocity", "vc_ratio", "hist_vel_mean", "delay_ratio"]:
        if k in df_aligned.columns:
            v = df_aligned[k].values[0]
            print(f"  df_aligned[{k}] = {v}")

    pred_idx = int(ppl.predict(df_aligned)[0])
    proba_arr = ppl.predict_proba(df_aligned)[0]
    pred_label = le.inverse_transform([pred_idx])[0]
    confidence = float(proba_arr[pred_idx])
    proba_dict = {le.inverse_transform([i])[0]: float(p) for i, p in enumerate(proba_arr)}

    print(f"  -> {pred_label} ({confidence:.4f})")
    print(f"  probs: " + ", ".join(f"{k}={v:.4f}" for k, v in proba_dict.items()))
    return pred_label, confidence, proba_dict


print(f"Model has {len(feature_names)} features")
print(f"Template has {len(tmpl)} keys")

print("\n--- Test 1: Free Flow (low vc, night, no rush) ---")
test_row("FREE", length=500, max_vel=30, vc=0.1, hour=2, is_wknd=False, is_rush=False)

print("\n--- Test 2: Gridlock (high vc, evening rush) ---")
test_row("GRID", length=4900, max_vel=110, vc=1.4, hour=17, is_wknd=False, is_rush=True)

print("\n--- Test 3: Mid (normal) ---")
test_row("MID", length=2000, max_vel=60, vc=0.5, hour=12, is_wknd=False, is_rush=False)
