"""
los_engine.py — HCM 2010/2022 Level of Service Engine.
Fast, deterministic, responsive to all user inputs.

Road type is inferred from max_velocity (speed limit):
  >= 80 km/h → Highway/Freeway (HCM Chapter 11)
  >= 50 km/h → Urban Arterial (HCM Chapter 19)
  <  50 km/h → Local/Residential (HCM Chapter 20)

LOS thresholds are calibrated on HCM standard values, with rush-hour and
weekend adjustments.
"""
from __future__ import annotations
import math
import joblib
from pathlib import Path

_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "los_engine_model.pkl"


# ── HCM LOS Thresholds ──────────────────────────────────────────────────────

# Highway/Freeway LOS by density (pc/mi/ln) — HCM Exhibit 11-2
HIGHWAY_DENSITY_THRESHOLDS = [11, 18, 26, 35, 45]   # A–B–C–D–E boundary

# Urban Arterial LOS by v/c ratio — HCM Exhibit 19-2
# Based on average travel speed as % of free-flow speed
URBAN_VC_THRESHOLDS = [
    0.00,   # LOS A: v/c ≤ 0.30
    0.30,   # LOS B
    0.45,   # LOS C
    0.60,   # LOS D
    0.75,   # LOS E
    0.90,   # LOS F
]

# Local/Residential street LOS by v/c ratio — HCM Chapter 20
LOCAL_VC_THRESHOLDS = [
    0.00,   # LOS A
    0.20,   # LOS B
    0.35,   # LOS C
    0.50,   # LOS D
    0.70,   # LOS E
    0.85,   # LOS F
]

# Rush-hour volume multipliers (apply to effective v/c)
RUSH_MULT = {
    (7, 8):  1.20, (8, 9):  1.25,   # morning peak
    (11, 12): 1.10, (12, 13): 1.08,   # lunch
    (16, 17): 1.30, (17, 18): 1.40,   # evening peak
    (18, 19): 1.25,
}
WEEKEND_MULT = 0.75   # weekends have ~25% less traffic

LOS_NAMES = {
    "A": "Tự do", "B": "Bình thường", "C": "Ổn định",
    "D": "Gần bão hòa", "E": "Kẹt xe", "F": "Tắc nghẽn",
}


def _rush_mult(hour: int, is_weekend: bool) -> float:
    if is_weekend:
        return WEEKEND_MULT
    for (h0, h1), mult in RUSH_MULT.items():
        if h0 <= hour < h1:
            return mult
    return 1.0


def _road_class(max_velocity: float) -> str:
    if max_velocity >= 80:
        return "highway"
    elif max_velocity >= 50:
        return "urban"
    return "local"


def _density_los(density: float) -> tuple[str, float]:
    """Highway: LOS from density (pc/mi/ln equivalent)."""
    thresh = HIGHWAY_DENSITY_THRESHOLDS
    letters = ["A", "B", "C", "D", "E", "F"]
    los = "F"
    conf = 0.5
    for i, t in enumerate(thresh):
        if density < t:
            los = letters[i]
            # Confidence: highest when deep within the band
            lo = thresh[i - 1] if i > 0 else 0
            center = (lo + t) / 2
            spread = (t - lo) / 2
            if spread > 0:
                z = abs(density - center) / spread
                conf = max(0.55, 1.0 - z * 0.3)
            else:
                conf = 0.85
            break
    return los, conf


def _vc_los(vc: float, road: str) -> tuple[str, float]:
    """Urban/Local: LOS from v/c ratio."""
    thresh = URBAN_VC_THRESHOLDS if road == "urban" else LOCAL_VC_THRESHOLDS
    letters = ["A", "B", "C", "D", "E", "F"]

    # Find which band
    los = "F"
    conf = 0.5
    for i in range(len(letters)):
        if vc <= thresh[i + 1]:
            lo = thresh[i]
            hi = thresh[i + 1]
            los = letters[i]
            # Confidence: deepest in middle of band
            if hi > lo:
                center = (lo + hi) / 2
                spread = (hi - lo) / 2
                z = abs(vc - center) / spread
                conf = max(0.55, 1.0 - z * 0.3)
            else:
                conf = 0.85
            break
    return los, conf


def _compute_probs(vc: float, road: str, rush: bool) -> dict[str, float]:
    """Gaussian-like probability distribution across LOS bands."""
    thresh = URBAN_VC_THRESHOLDS if road == "urban" else LOCAL_VC_THRESHOLDS
    if road == "highway":
        # Use density
        density = vc * 40  # approximate from effective vc
        bounds = [0] + HIGHWAY_DENSITY_THRESHOLDS + [100]
    else:
        bounds = [0] + thresh + [5.0]  # extended upper bound

    letters = ["A", "B", "C", "D", "E", "F"]
    probs = {l: 0.0 for l in letters}

    if road == "highway":
        val = density
    else:
        val = vc

    for i in range(len(letters)):
        lo = bounds[i]
        hi = bounds[i + 1]
        if lo <= val <= hi:
            center = (lo + hi) / 2
            spread = max(hi - lo, 0.01)
            z = abs(val - center) / spread
            probs[letters[i]] = max(0.01, 1.0 - z * 0.5)
            # Adjacent band spillover
            if i > 0:
                lo2, hi2 = bounds[i - 1], lo
                adj_c = (lo2 + hi2) / 2
                adj_s = max(hi2 - lo2, 0.01)
                z2 = abs(val - adj_c) / adj_s
                probs[letters[i - 1]] = max(0.01, 0.35 * (1.0 - z2 * 0.5))
            if i < len(letters) - 1:
                lo2, hi2 = hi, bounds[i + 2]
                adj_c = (lo2 + hi2) / 2
                adj_s = max(hi2 - lo2, 0.01)
                z2 = abs(val - adj_c) / adj_s
                probs[letters[i + 1]] = max(0.01, 0.35 * (1.0 - z2 * 0.5))

    # Rush-hour sharpening: reduces confidence in good LOS
    if rush and probs.get("A", 0) > 0.3:
        probs["A"] *= 0.5
        probs["B"] *= 0.8

    # Normalize
    total = sum(probs.values())
    if total > 0:
        probs = {k: v / total for k, v in probs.items()}

    return probs


# ── Main function ────────────────────────────────────────────────────────────

def compute_los(
    length: float,
    max_velocity: float,
    vc_ratio: float,
    hour: int,
    is_weekend: bool,
    is_rush: bool,
) -> tuple[str, float, dict[str, float]]:
    """
    HCM-based LOS computation.

    Returns: (los_label, confidence, {letter: probability})
    """
    vc_base = max(0.0, min(float(vc_ratio), 4.0))
    ffs = float(max_velocity)
    road = _road_class(ffs)

    # Effective v/c after time-of-day adjustment
    rm = _rush_mult(hour, is_weekend)
    vc_eff = vc_base * rm
    vc_eff = max(0.0, min(vc_eff, 4.0))

    if road == "highway":
        # LOS by density (vehicles per mile per lane)
        # Density = (vc * capacity) / speed ≈ vc * 40 (rough scaling)
        density = vc_eff * 40
        los, conf = _density_los(density)
    else:
        los, conf = _vc_los(vc_eff, road)

    # Probability distribution
    probs = _compute_probs(vc_eff, road, is_rush)
    conf = probs.get(los, 0.5)

    return los, conf, probs


# ── Trained model fallback ────────────────────────────────────────────────────

def _try_trained_model(
    length: float,
    max_velocity: float,
    vc_ratio: float,
    hour: int,
    is_weekend: bool,
    is_rush: bool,
) -> tuple[str, float, dict[str, float]] | None:
    """Use trained RF if available and functional. Otherwise returns None."""
    if not _MODEL_PATH.exists():
        return None
    try:
        import joblib as jl
        data = jl.load(_MODEL_PATH)
        model = data["model"]
        le = data["le"]

        import pandas as pd, math
        row = {
            "length":             length,
            "max_velocity":       max_velocity,
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
            "road_type":       2 if max_velocity >= 80 else 1 if max_velocity >= 50 else 0,
            "vc_norm":         vc_ratio / max(max_velocity, 1) * 100,
            "length_log":     math.log1p(length),
        }
        X = pd.DataFrame([row])
        idx = int(model.predict(X)[0])
        # Guard: make sure idx is valid for the label encoder
        if idx < 0 or idx >= len(le.classes_):
            return None
        ps = model.predict_proba(X)[0]
        if len(ps) != len(le.classes_):
            return None
        pred = le.inverse_transform([idx])[0]
        conf = float(ps[idx])
        proba = dict(zip(le.classes_, [float(p) for p in ps]))
        return pred, conf, proba
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def predict_ui(
    length: float,
    max_velocity: float,
    vc_ratio: float,
    hour: int,
    is_weekend: bool,
    is_rush: bool,
) -> tuple[str, float, dict[str, float]]:
    """Predict LOS. Returns (los_label, confidence, {letter: probability})."""
    trained = _try_trained_model(length, max_velocity, vc_ratio, hour, is_weekend, is_rush)
    if trained is not None:
        return trained
    return compute_los(length, max_velocity, vc_ratio, hour, is_weekend, is_rush)
