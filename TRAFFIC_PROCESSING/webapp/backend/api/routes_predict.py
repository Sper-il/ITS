"""
routes_predict.py. JSON API for the Quick Predict tab.

POST /api/predict  → body {length, max_velocity, vc_ratio, hour, is_weekend, is_rush}

Uses the dedicated los_engine for responsive, physics-based predictions.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.core.constants import LOS_ADVICE, LOS_COLORS, LOS_DESC, LOS_NAMES

bp = Blueprint("predict", __name__, url_prefix="/api")


@bp.post("/predict")
def predict():
    body = request.get_json(silent=True) or {}
    try:
        length       = float(body.get("length", 500))
        max_velocity = float(body.get("max_velocity", 60))
        vc_ratio     = float(body.get("vc_ratio", 0.5))
        hour         = int(body.get("hour", 18))
        is_weekend   = bool(body.get("is_weekend", False))
        is_rush      = bool(body.get("is_rush", False))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid input"}), 400

    try:
        # los_engine returns (label, confidence, {letter: proba})
        from backend.core.los_engine import predict_ui
        label, confidence, proba = predict_ui(
            length, max_velocity, vc_ratio, hour, is_weekend, is_rush,
        )
    except Exception as ex:
        return jsonify({"error": f"{type(ex).__name__}: {str(ex)[:200]}"}), 500

    advice_text, advice_color = LOS_ADVICE.get(label, ("", "#888"))
    probability_bars = []
    for letter in "ABCDEF":
        probability_bars.append({
            "letter":  letter,
            "label":   f"{letter} · {LOS_NAMES[letter]}",
            "color":   LOS_COLORS[letter],
            "value":   round(float(proba.get(letter, 0.0)), 4),
            "percent": round(float(proba.get(letter, 0.0)) * 100, 1),
        })

    return jsonify({
        "prediction":   label,
        "name":         LOS_NAMES[label],
        "description":  LOS_DESC[label],
        "color":        LOS_COLORS[label],
        "advice":       advice_text,
        "advice_color": advice_color,
        "confidence":   round(confidence, 4),
        "probability":  probability_bars,
        "input": {
            "length_m":    length,
            "speed_kmh":   max_velocity,
            "vc_ratio":    vc_ratio,
            "hour":        hour,
            "is_weekend":  is_weekend,
            "is_rush":     is_rush,
        },
        "raw_features": {
            "length":         length,
            "max_velocity":   max_velocity,
            "vc_ratio":      vc_ratio,
            "hour":          hour,
            "is_weekend":   is_weekend,
            "is_rush":       is_rush,
        },
    })
