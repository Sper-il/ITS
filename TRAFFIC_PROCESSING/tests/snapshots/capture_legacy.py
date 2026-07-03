"""
capture_legacy.py — Capture snapshots from the LEGACY `app.py` before refactor.

Why a separate script?  Importing `app.py` runs `st.set_page_config(...)`,
`st.markdown(...)`, the three `st.tabs(...)` calls, and the whole Tab 3
block (which builds a real Folium map) at module top-level.  That all
fails outside a Streamlit runtime.  We mock the streamlit module *before*
importing app so module-level side-effects become no-ops.

Run once BEFORE refactor; the result files become the golden baseline
that `capture_baseline.py` is compared against after refactor.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import sys
import types
from datetime import datetime
from pathlib import Path
from unittest import mock

THIS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = THIS_DIR.parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

PINNED_DT = datetime(2026, 6, 18, 9, 0, 0)


# ---------------------------------------------------------------------------
# Mock the streamlit module so app.py can be imported outside a runtime.
# We need:
#   * cache_resource / cache_data → identity decorators
#   * set_page_config / markdown / tabs / image / sidebar / etc. → no-ops
#   * session_state → dict subclass with attribute access
#   * columns(...).__enter__ pattern (Streamlit returns a context manager)
#   * spinner(...).__enter__ pattern
#   * streamlit_js_eval / pydeck / folium / streamlit_folium / st_autorefresh
# ---------------------------------------------------------------------------
class _DummyCM:
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _SessionState(dict):
    """Dict that also supports attribute access (Streamlit's SessionState)."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None
    def __setattr__(self, key, value):
        self[key] = value


def _make_fake_streamlit():
    fake_st = types.ModuleType("streamlit")

    def _identity_cache(*dargs, **dkwargs):
        def deco(fn):
            return fn
        return deco

    fake_st.cache_resource = _identity_cache
    fake_st.cache_data = _identity_cache
    fake_st.set_page_config = lambda *a, **kw: None

    # Every other st.* call should be a no-op.  Use MagicMock so that chained
    # attribute access (e.g. ``st.sidebar.markdown(...)``) also returns a
    # no-op mock.
    mm = mock.MagicMock()
    # Copy every method we use onto the fake module so chained attribute
    # access (e.g. ``st.sidebar.markdown(...)``) returns a no-op mock.
    for name in (
        "markdown", "image", "divider", "button", "tab",
        "plotly_chart", "metric", "slider", "checkbox",
        "selectbox", "text_input", "caption", "success", "warning", "error",
        "info", "toast", "json", "progress", "stop", "rerun",
        "empty", "container", "write", "code", "subheader", "header",
        "balloons", "snow", "popover", "status", "form", "form_submit_button",
        "download_button",
    ):
        setattr(fake_st, name, getattr(mm, name))

    # MagicMock's __call__ returns a single mock.  Streamlit's `st.columns(n)`
    # returns a tuple/list of n column-mocks.  Patch it explicitly so
    # ``header_col, toggle_col = st.columns([0.78, 0.22])`` style unpacking
    # works.
    def _columns(spec, **kw):
        if isinstance(spec, int):
            n = spec
        else:
            n = len(spec)
        return tuple(mm for _ in range(n))

    fake_st.columns = _columns
    fake_st.tabs = lambda labels: tuple(_DummyCM() for _ in labels)
    fake_st.sidebar = mm
    fake_st.spinner = lambda *a, **kw: _DummyCM()
    fake_st.expander = lambda *a, **kw: _DummyCM()

    # Slider / checkbox / selectbox / text_input must return real values, not
    # MagicMock, because their results feed into the pure-function calls
    # (e.g. `_predict_cached(length, ...)` at module top-level).  We return
    # the ``default`` arg if provided, else a sane fallback.
    def _slider(label, min_value=0, max_value=100, value=None, step=1, **kw):
        return min_value if value is None else value
    def _checkbox(label, value=False, **kw):
        return value
    def _selectbox(label, options=(), index=0, **kw):
        return options[index] if options else ""
    def _text_input(label, value="", **kw):
        return value
    def _number_input(label, min_value=0, max_value=100, value=0, **kw):
        return value
    fake_st.slider = _slider
    fake_st.checkbox = _checkbox
    fake_st.selectbox = _selectbox
    fake_st.text_input = _text_input
    fake_st.number_input = _number_input

    fake_st.session_state = _SessionState(theme_light=False)

    # Components
    fake_st.components = types.ModuleType("streamlit.components")
    fake_st.components.v1 = types.ModuleType("streamlit.components.v1")
    fake_st.components.v1.html = lambda *a, **kw: None

    # Third-party imports that app.py does at top-level
    # (streamlit_folium, streamlit_js_eval, streamlit_autorefresh)
    sys.modules.setdefault("streamlit_folium", types.ModuleType("streamlit_folium"))
    sys.modules["streamlit_folium"].st_folium = lambda *a, **kw: {}

    sys.modules.setdefault("streamlit_js_eval", types.ModuleType("streamlit_js_eval"))
    sys.modules["streamlit_js_eval"].streamlit_js_eval = None

    sys.modules.setdefault("streamlit_autorefresh", types.ModuleType("streamlit_autorefresh"))
    sys.modules["streamlit_autorefresh"].st_autorefresh = lambda **kw: None

    return fake_st


def _install_fake_streamlit():
    if "streamlit" in sys.modules:
        return
    fake_st = _make_fake_streamlit()
    sys.modules["streamlit"] = fake_st
    sys.modules.setdefault("streamlit.components", fake_st.components)
    sys.modules.setdefault("streamlit.components.v1", fake_st.components.v1)


def _import_refactored():
    """Import the refactored streamlit_app.lib modules (no streamlit stub needed)."""
    return importlib.import_module("streamlit_app.lib")


# ---------------------------------------------------------------------------
# Payload builders (mirror the post-refactor capture_baseline.py)
# ---------------------------------------------------------------------------
def _round_floats(obj, ndigits: int = 6):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, ndigits) for v in obj]
    return obj


def build_predict_single(model) -> dict:
    pred_label, confidence, proba_dict = model.predict_cached(
        length=500, max_velocity=60, vc_ratio=0.5,
        hour=14, is_weekend=0, is_rush=0,
    )
    return {
        "pred_label": str(pred_label),
        "confidence": float(confidence),
        "proba_dict": {str(k): float(v) for k, v in sorted(proba_dict.items())},
    }


def build_edge_features_tiny(model, edge_features) -> dict:
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

    feat_df = edge_features.build_edge_feature_table(G, hour=8, weekday=2)
    records = []
    for _, row in feat_df.iterrows():
        records.append({k: _round_floats(v) for k, v in row.items()})
    return {
        "n_rows": int(feat_df.shape[0]),
        "n_cols": int(feat_df.shape[1]),
        "columns": list(feat_df.columns),
        "rows": records,
    }


def build_live_predictions(model) -> dict:
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
            return np.full((n, 6), 1.0 / 6.0)

    class FakeLabelEncoder:
        classes_ = np.array(list("ABCDEF"))
        def inverse_transform(self, y):
            return np.array([self.classes_[i] for i in y])

    def fake_load_model():
        return FakePipeline(), FakeLabelEncoder(), ["length", "max_velocity", "vc_ratio"]

    def fake_load_test_data():
        return fake_df

    with mock.patch.object(model, "load_model", side_effect=fake_load_model), \
         mock.patch.object(model, "load_test_data", side_effect=fake_load_test_data):
        fn = model.get_live_predictions_cached
        result = fn.__wrapped__(n) if hasattr(fn, "__wrapped__") else fn(n)

    return {
        "n_rows": int(result.shape[0]),
        "columns": list(result.columns),
        "los_pred_value_counts": {str(k): int(v) for k, v in result["LOS_pred"].value_counts().items()},
        "confidence_min": float(result["confidence"].min()),
        "confidence_max": float(result["confidence"].max()),
        "confidence_mean": float(result["confidence"].mean()),
    }


def build_routing_graph_meta(model) -> dict:
    models_dir = model.MODELS_DIR
    feat_path = models_dir / "feature_names_used.json"
    metrics_path = models_dir / "training_metrics.json"
    with open(feat_path, "r", encoding="utf-8") as f:
        feat = json.load(f)
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)
    return {
        "feature_names_n": len(feat["feature_names"]),
        "feature_names_first10": feat["feature_names"][:10],
        "feature_names_last10": feat["feature_names"][-10:],
        "feature_names": feat["feature_names"],
        "metrics_keys": sorted(metrics.keys()),
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def _write_snapshot(name: str, payload: dict) -> Path:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    wrapped = {"sha256": sha, "data": payload}
    out = THIS_DIR / name
    out.write_text(
        json.dumps(wrapped, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    print(f"  wrote {out.name:30s}  sha256={sha[:16]}…")
    return out


def main():
    print("[capture_legacy] importing refactored streamlit_app.lib …")
    lib = _import_refactored()
    from streamlit_app.lib import edge_features as ef_lib
    model = lib.model
    edge_features = ef_lib

    # Pin datetime.now() so pure functions that read it produce stable output.
    import datetime as dt_mod
    with mock.patch.object(dt_mod, "datetime", wraps=dt_mod.datetime) as fake_dt:
        fake_dt.now.return_value = PINNED_DT
        print("[1/4] predict_single …")
        _write_snapshot("predict_single.json", build_predict_single(model))
        print("[2/4] edge_features_tiny …")
        _write_snapshot("edge_features_tiny.json", build_edge_features_tiny(model, edge_features))
        print("[3/4] live_predictions_50 …")
        _write_snapshot("live_predictions_50.json", build_live_predictions(model))
    print("[4/4] routing_graph_meta …")
    _write_snapshot("routing_graph_meta.json", build_routing_graph_meta(model))
    print("[capture_legacy] done.")


if __name__ == "__main__":
    main()
