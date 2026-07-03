"""
routes_meta.py. Misc endpoints: model info, health, validation metrics.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..core.constants import DEFAULT_METRICS, LOS_COLORS, LOS_NAMES
from ..core.model import load_training_metrics


bp = Blueprint("meta", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/model/info")
def model_info():
    try:
        m = load_training_metrics()
        return jsonify({
            "metrics": DEFAULT_METRICS,
            "val_accuracy":      m.get("val_accuracy"),
            "val_macro_f1":      m.get("val_macro_f1"),
            "cv_accuracy_mean":  m.get("cv_accuracy_mean"),
            "n_classes":         len(LOS_COLORS),
            "class_labels":      list(LOS_COLORS.keys()),
            "class_names":       {k: LOS_NAMES[k] for k in LOS_COLORS},
            "class_colors":      LOS_COLORS,
        })
    except Exception as ex:
        return jsonify({
            "metrics": DEFAULT_METRICS,
            "error":   f"{type(ex).__name__}: {str(ex)[:140]}",
        })
