"""
routes_overview.py. JSON API for the Overview tab.

GET /api/overview/summary       → top-level KPIs (sample size, mean conf, dominant LOS)
GET /api/overview/distribution  → 6-class counts + percentages + colors
GET /api/overview/f1            → per-class F1 from training_metrics.json
GET /api/overview/confidence    → histogram of confidence values (24 bins)
"""
from __future__ import annotations

from collections import Counter

import numpy as np
from flask import Blueprint, jsonify

from ..core.constants import LOS_COLORS, LOS_NAMES, DEFAULT_METRICS
from ..core.model import (
    get_live_predictions,
    load_training_metrics,
)


bp = Blueprint("overview", __name__, url_prefix="/api/overview")


@bp.get("/summary")
def summary():
    df = get_live_predictions(1000)
    counts = Counter(df["LOS_pred"].tolist())
    n = sum(counts.values())
    avg_conf = float(df["confidence"].mean())
    dominant = max(counts, key=counts.get) if counts else "B"
    return jsonify({
        "samples":       int(n),
        "mean_conf":     round(avg_conf, 4),
        "dominant_los":  dominant,
        "dominant_name": LOS_NAMES.get(dominant, ""),
        "dominant_color": LOS_COLORS.get(dominant, "#2563eb"),
        "validation":    DEFAULT_METRICS,
    })


@bp.get("/distribution")
def distribution():
    df = get_live_predictions(1000)
    counts = Counter(df["LOS_pred"].tolist())
    n = max(sum(counts.values()), 1)
    rows = []
    for letter in "ABCDEF":
        c = counts.get(letter, 0)
        rows.append({
            "letter":    letter,
            "name":      LOS_NAMES[letter],
            "color":     LOS_COLORS[letter],
            "count":     int(c),
            "percent":   round(c / n * 100, 2),
        })
    return jsonify({"labels": [r["letter"] for r in rows], "rows": rows, "total": n})


@bp.get("/f1")
def f1_per_class():
    m = load_training_metrics()
    report = m.get("classification_report", {})
    rows = []
    for letter in "ABCDEF":
        key = f"LOS_{letter}"
        r = report.get(key, {})
        rows.append({
            "letter":  letter,
            "color":   LOS_COLORS[letter],
            "name":    LOS_NAMES[letter],
            "f1":      round(float(r.get("f1-score", 0.0)), 4),
            "support": int(r.get("support", 0)),
        })
    return jsonify({"rows": rows})


@bp.get("/confidence")
def confidence_histogram():
    df = get_live_predictions(1000)
    arr = df["confidence"].values
    counts, edges = np.histogram(arr, bins=24, range=(0.0, 1.0))
    return jsonify({
        "bins":   [round(float(e), 4) for e in edges],
        "counts": [int(c) for c in counts],
    })
