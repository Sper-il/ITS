"""
model.py. Trained-model loading, feature alignment, and prediction entry points.

Refactored from streamlit_app/lib/model.py to remove Streamlit dependency.
All caching wrappers replaced with manual LRU-style cache + module-level globals
(FastAPI/Flask handle per-request lifecycle; the model is loaded once per process).

Exposed functions:
- load_model()                       → (pipeline, label_encoder, feature_names)
- load_training_metrics()            → dict
- load_test_data()                   → pandas DataFrame
- align_features(df, features)       → pandas DataFrame
- predict_row(length, max_vel, vc, hour, is_weekend, is_rush) → (label, conf, proba)
- get_live_predictions(n)            → DataFrame with columns [LOS_pred, confidence]
"""
from __future__ import annotations

import json
import threading
from functools import lru_cache
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

from .paths import DATA_AFTER_SPLIT_DIR, MODELS_DIR, OUTPUTS_DIR


# ── Process-wide caches (loaded once, locked for thread safety) ──
_model_lock = threading.Lock()
_ppl = None
_label_encoder = None
_feature_names: list[str] | None = None
_default_template: dict[str, Any] | None = None


def load_model():
    """Load stacking pipeline + label encoder + feature names once per process."""
    global _ppl, _label_encoder, _feature_names, _default_template
    with _model_lock:
        if _ppl is None:
            _ppl = joblib.load(MODELS_DIR / "stacking_ensemble_ITS.joblib")
            _label_encoder = joblib.load(MODELS_DIR / "los_label_encoder.joblib")
            with open(MODELS_DIR / "feature_names_used.json", "r", encoding="utf-8") as f:
                feat_meta = json.load(f)
            _feature_names = feat_meta["feature_names"]
            _default_template = feat_meta.get("default_template", {})
    return _ppl, _label_encoder, _feature_names


@lru_cache(maxsize=1)
def load_training_metrics() -> dict:
    """Read training_metrics.json. Cached for the lifetime of the process."""
    with open(MODELS_DIR / "training_metrics.json", "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_test_data() -> pd.DataFrame:
    """Load the primary labelled dataset (~33K rows), fallback to placeholder test.csv."""
    primary = OUTPUTS_DIR / "train_features.csv"
    fallback = DATA_AFTER_SPLIT_DIR / "test" / "test.csv"
    src = primary if primary.exists() else fallback
    return pd.read_csv(src, low_memory=False)


def align_features(df: pd.DataFrame, expected_features: list[str]) -> pd.DataFrame:
    """Re-order / fill / drop columns of df to match expected_features."""
    missing = set(expected_features) - set(df.columns)
    extra = set(df.columns) - set(expected_features)
    if missing:
        df = pd.concat(
            [df, pd.DataFrame(np.nan, index=df.index, columns=list(missing))], axis=1
        )
    if extra:
        df = df.drop(columns=list(extra))
    return df[expected_features]


def _feature_default_template() -> dict[str, Any]:
    """Median values for every non-user feature (computed once from train set)."""
    global _default_template
    if _default_template:          # empty dict {} is falsy → triggers load
        return _default_template
    load_model()
    if _default_template:           # loaded from JSON or computed medians
        return _default_template
    # Fall back to medians from the labelled CSV
    df = load_test_data()
    num = df.select_dtypes(include="number")
    _default_template = {c: float(num[c].median()) for c in num.columns if c not in {"los_label", "LOS"}}
    return _default_template


def predict_row(
    length: float,
    max_velocity: float,
    vc_ratio: float,
    hour: int,
    is_weekend: bool,
    is_rush: bool,
) -> tuple[str, float, dict[str, float]]:
    """Single-row LOS prediction. Returns (label, confidence, {label: proba})."""
    ppl, le, feature_names = load_model()
    template = _feature_default_template()

    row: dict[str, Any] = dict(template)
    # Override user-controlled features (use model's exact feature names)
    import math
    overrides = {
        "length": length,
        "max_velocity": max_velocity,
        "max_velocity_kmh": max_velocity,
        "vc_ratio": vc_ratio,
        "period_hour": int(hour),
        "is_weekend": int(bool(is_weekend)),
        "is_rush_hour": int(bool(is_rush)),
        # Derived: cyclic hour encoding
        "hour_sin": math.sin(2 * math.pi * hour / 24),
        "hour_cos": math.cos(2 * math.pi * hour / 24),
        # Derived: rush flags
        "is_morning_rush": int(7 <= hour <= 9),
        "is_evening_rush": int(16 <= hour <= 19),
        "is_night": int(hour >= 22 or hour <= 5),
        "is_working_hours": int(8 <= hour <= 17 and not is_weekend),
        "is_lunch": int(11 <= hour <= 13),
        # Derived: normalized values (using typical ranges from training data)
        "length_norm": length / 5000.0,
        "max_velocity_norm": max_velocity / 120.0,
        # Derived: period
        "period_minutes_of_day": hour * 60,
        "period_minute": 0,
        "period_hour_norm": hour / 23.0,
        "period_minutes_of_day_norm": (hour * 60) / 1439.0,
        # Derived: interaction features
        "vc_x_hour": vc_ratio * hour,
        "vc_x_weekday": vc_ratio * (5 if is_weekend else 2),
        "length_x_vc": length * vc_ratio,
        "weekend_x_rush": int(is_weekend and is_rush),
    }
    for k, v in overrides.items():
        if k in row:
            row[k] = v

    # Build an aligned DataFrame in the exact column order
    df_in = pd.DataFrame([row])
    df_aligned = align_features(df_in, feature_names)

    pred_idx = int(ppl.predict(df_aligned)[0])
    proba_arr = ppl.predict_proba(df_aligned)[0]
    pred_label = le.inverse_transform([pred_idx])[0]
    confidence = float(proba_arr[pred_idx])
    proba_dict = {
        le.inverse_transform([i])[0]: float(p) for i, p in enumerate(proba_arr)
    }
    return pred_label, confidence, proba_dict


def get_live_predictions(n: int = 1000, seed: int = 42) -> pd.DataFrame:
    """Bulk predictions over a sample of the test split. Used by Overview tab."""
    ppl, le, feature_names = load_model()
    df = load_test_data()
    sample = df.sample(n=min(n, len(df)), random_state=seed).reset_index(drop=True)

    truth_col = None
    if "los_label" in sample.columns:
        truth_col = "los_label"
    elif "LOS" in sample.columns:
        truth_col = "LOS"

    X = align_features(sample.drop(columns=[truth_col]) if truth_col else sample, feature_names)
    pred_idx = ppl.predict(X)
    pred_labels = le.inverse_transform(pred_idx.astype(int))
    proba = ppl.predict_proba(X)
    conf = proba[np.arange(len(proba)), pred_idx.astype(int)]

    out = pd.DataFrame({
        "LOS_pred": pred_labels,
        "confidence": conf,
    })
    if truth_col:
        out["LOS_true"] = sample[truth_col].values
    return out
