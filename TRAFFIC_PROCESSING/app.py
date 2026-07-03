"""
app.py. ITS Traffic LOS Dashboard, Flask entry point.

Replaces the legacy Streamlit app. The Flask app:
- Serves the static frontend (HTML/CSS/JS) from webapp/static/.
- Exposes JSON API routes under /api/*.

Run:
    python app.py            # serves on http://127.0.0.1:8000
    python app.py --port N   # custom port

The legacy Streamlit app (streamlit_app/, app.py at project root,
.streamlit/) is now obsolete. Use this file as the new entry point.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ── CRITICAL: must come BEFORE any `from backend` imports ──────────────────
# VSCode's language server evaluates imports without executing the script body,
# so sys.path must be patched at module-load time.  Resolving webapp/ relative
# to this file (TRAFFIC_PROCESSING/app.py) guarantees the correct directory.
_WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"
if str(_WEBAPP_DIR) not in sys.path:
    sys.path.insert(0, str(_WEBAPP_DIR))
# ──────────────────────────────────────────────────────────────────────────

from flask import Flask, make_response, send_from_directory  # noqa: E402

from backend.api.routes_meta import bp as meta_bp       # noqa: E402
from backend.api.routes_overview import bp as overview_bp  # noqa: E402
from backend.api.routes_predict import bp as predict_bp  # noqa: E402
from backend.api.routes_routing import bp as routing_bp  # noqa: E402


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(_WEBAPP_DIR / "static"),
        static_url_path="",
    )
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # ── API blueprints ──
    app.register_blueprint(meta_bp)
    app.register_blueprint(overview_bp)
    app.register_blueprint(predict_bp)
    app.register_blueprint(routing_bp)

    # ── Static frontend ──
    @app.after_request
    def _no_cache(resp):
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "overview_dashboard.html")

    @app.get("/overview")
    def page_overview():
        return send_from_directory(app.static_folder, "overview_dashboard.html")

    @app.get("/predict")
    def page_predict():
        return send_from_directory(app.static_folder, "quick_predict_redesigned.html")

    @app.get("/routing")
    def page_routing():
        resp = make_response(send_from_directory(app.static_folder, "routing_empty_state.html"))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @app.get("/routing/found")
    def page_routing_found():
        return send_from_directory(app.static_folder, "routing_route_found.html")

    @app.get("/routing/empty")
    def page_routing_empty():
        return send_from_directory(app.static_folder, "routing_empty_state.html")

    @app.get("/navigation")
    def page_nav():
        return send_from_directory(app.static_folder, "full_screen_navigation.html")

    return app


# Eagerly warm the model + graph cache so the first request doesn't pay
# the full load cost.
def _warm_caches() -> None:
    try:
        from backend.core.model import load_model
        load_model()
    except Exception as ex:
        print(f"[warn] could not preload model: {ex}", file=sys.stderr)
    try:
        from backend.core.routing_engine import _load_graph
        _load_graph()
    except Exception as ex:
        print(f"[warn] could not preload routing graph: {ex}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    _warm_caches()
    app = create_app()
    print(f"\nITS Traffic LOS · listening on http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)
