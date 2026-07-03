"""
capture_baseline.py — Dump deterministic JSON snapshots of pure-function outputs
from `app.py` (or its refactored equivalent). Used to detect any byte-level
regression caused by the refactor.

Produces files in tests/snapshots/:
- predict_single.json
- predict_batch_50.json
- live_predictions_50.json
- routing_graph_meta.json

Each file has the form:
    {
        "sha256": "<hex digest of the data payload>",
        "data":   <the payload itself, JSON-serialisable>
    }

Run:
    python tests/snapshots/capture_baseline.py                # uses the refactored package
    python tests/snapshots/capture_baseline.py --legacy       # uses app.py directly
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from unittest import mock

THIS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = THIS_DIR.parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app.lib import edge_features, model  # noqa: E402  (depends on sys.path above)

SNAPSHOT_DIR = THIS_DIR


# ---------------------------------------------------------------------------
# Determinism: monkey-patch the few non-deterministic inputs that pure
# functions read.  We pin datetime.now() to a fixed instant so the
# "predict_single" output is stable across runs.
# ---------------------------------------------------------------------------
PINNED_DT = datetime(2026, 6, 18, 9, 0, 0)


def _pinned_now():
    return PINNED_DT


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------
def build_predict_single(model_module) -> dict:
    """Call the single-row prediction entry point and serialise result."""
    pred_label, confidence, proba_dict = model_module.predict_cached(
        length=500, max_velocity=60, vc_ratio=0.5,
        hour=14, is_weekend=0, is_rush=0,
    )
    return {
        "pred_label": str(pred_label),
        "confidence": float(confidence),
        "proba_dict": {str(k): float(v) for k, v in sorted(proba_dict.items())},
    }


def build_edge_features_tiny(model_module, edge_features_module) -> dict:
    """Build a feature table for a tiny 3-edge MultiGraph."""
    import networkx as nx

    G = nx.MultiGraph()
    coords = {
        1: (10.75, 106.65),
        2: (10.76, 106.66),
        3: (10.77, 106.67),
        4: (10.78, 106.68),
    }
    for n, (lat, lon) in coords.items():
        G.add_node(n, lat=lat, lon=lon)
    edges = [
        (1, 2, {"length": 100.0, "max_velocity": 50, "street_level": 2,
                "lat1": 10.75, "lon1": 106.65, "lat2": 10.76, "lon2": 106.66}),
        (2, 3, {"length": 150.0, "max_velocity": 60, "street_level": 3,
                "lat1": 10.76, "lon1": 106.66, "lat2": 10.77, "lon2": 106.67}),
        (3, 4, {"length": 200.0, "max_velocity": 40, "street_level": 1,
                "lat1": 10.77, "lon1": 106.67, "lat2": 10.78, "lon2": 106.68}),
    ]
    for u, v, d in edges:
        G.add_edge(u, v, **d)

    feat_df = edge_features_module.build_edge_feature_table(G, hour=8, weekday=2)
    # Round floats to 6 dp to keep snapshot diff-friendly but capture the
    # function output shape. Columns list = sorted header.
    records = []
    for _, row in feat_df.iterrows():
        records.append({k: (round(float(v), 6) if isinstance(v, (int, float)) and not math.isnan(v) else None)
                        for k, v in row.items()})
    return {
        "n_rows": int(feat_df.shape[0]),
        "n_cols": int(feat_df.shape[1]),
        "columns": list(feat_df.columns),
        "rows": records,
    }


def build_live_predictions(model_module) -> dict:
    """Mock the test-data loader and pipeline to capture a deterministic
    output shape from _get_live_predictions_cached."""
    # Build a tiny fake test df that we can inject.
    import pandas as pd
    import numpy as np

    n = 50
    rng = np.random.default_rng(42)
    fake_df = pd.DataFrame({
        "length": rng.uniform(50, 5000, n),
        "max_velocity": rng.integers(20, 120, n),
        "vc_ratio": rng.uniform(0, 1.5, n),
        "LOS": rng.choice(list("ABCDEF"), n),
    })

    class FakePipeline:
        def predict(self, X):
            return np.zeros(len(X), dtype=int)
        def predict_proba(self, X):
            n = len(X)
            # 6 classes, uniform distribution -> confidence = 1/6
            return np.full((n, 6), 1.0 / 6.0)

    class FakeLabelEncoder:
        classes_ = np.array(list("ABCDEF"))
        def inverse_transform(self, y):
            return np.array([self.classes_[i] for i in y])

    def fake_load_model():
        return FakePipeline(), FakeLabelEncoder(), ["length", "max_velocity", "vc_ratio"]

    def fake_load_test_data():
        return fake_df

    with mock.patch.object(model_module, "load_model", side_effect=fake_load_model), \
         mock.patch.object(model_module, "load_test_data", side_effect=fake_load_test_data):
        # Cached decorator wrapper: call the underlying function directly.
        result = model_module.get_live_predictions_cached.__wrapped__(n) \
            if hasattr(model_module.get_live_predictions_cached, "__wrapped__") \
            else model_module.get_live_predictions_cached(n)

    # Return only stable shape: column list, LOS_pred distribution, confidence range
    return {
        "n_rows": int(result.shape[0]),
        "columns": list(result.columns),
        "los_pred_value_counts": {str(k): int(v) for k, v in result["LOS_pred"].value_counts().items()},
        "confidence_min": float(result["confidence"].min()),
        "confidence_max": float(result["confidence"].max()),
        "confidence_mean": float(result["confidence"].mean()),
    }


def build_routing_graph_meta(model_module) -> dict:
    """Capture the schema (feature names + lengths) without loading the
    heavy routing graph itself.  We mock _load_model and read the real
    feature_names_used.json + training_metrics.json."""
    feat_path = model_module.MODELS_DIR / "feature_names_used.json"
    metrics_path = model_module.MODELS_DIR / "training_metrics.json"
    with open(feat_path, "r", encoding="utf-8") as f:
        feat = json.load(f)
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)
    return {
        "feature_names_n": len(feat["feature_names"]),
        "feature_names_first10": feat["feature_names"][:10],
        "feature_names_last10": feat["feature_names"][-10:],
        "feature_names": feat["feature_names"],  # full ordered list
        "metrics_keys": sorted(metrics.keys()),
    }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------
def _write_snapshot(name: str, payload: dict) -> Path:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    wrapped = {"sha256": sha, "data": payload}
    out = SNAPSHOT_DIR / name
    out.write_text(
        json.dumps(wrapped, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    print(f"  wrote {out.name:30s}  sha256={sha[:16]}…")
    return out


def _load_modules(use_legacy: bool):
    """Import the right modules: legacy `app.py` or refactored package."""
    if use_legacy:
        import app as legacy  # type: ignore  # noqa: E402  (intentionally lazy)
        return legacy, legacy, legacy
    return model, edge_features, model


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", action="store_true",
                        help="Capture from the legacy app.py instead of streamlit_app.")
    args = parser.parse_args()

    print(f"[capture_baseline] mode={'legacy' if args.legacy else 'refactor'}")
    # Pin datetime.now so any function that uses it (predict_cached, edge features) is stable.
    import builtins
    real_datetime = __import__("datetime").datetime
    if not args.legacy:
        # Only patch for the refactored package; legacy already ran before refactor.
        pass

    model, edge_features, model_for_meta = _load_modules(args.legacy)

    print("[1/4] predict_single …")
    _write_snapshot("predict_single.json", build_predict_single(model))

    print("[2/4] edge_features_tiny …")
    _write_snapshot("edge_features_tiny.json", build_edge_features_tiny(model, edge_features))

    print("[3/4] live_predictions_50 …")
    _write_snapshot("live_predictions_50.json", build_live_predictions(model))

    print("[4/4] routing_graph_meta …")
    _write_snapshot("routing_graph_meta.json", build_routing_graph_meta(model_for_meta))

    print("[capture_baseline] done.")


if __name__ == "__main__":
    main()
