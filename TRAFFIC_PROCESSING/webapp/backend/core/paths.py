"""
paths.py. Centralised filesystem paths. No Streamlit import.
"""
from __future__ import annotations

from pathlib import Path

# webapp/backend/core/paths.py → TRAFFIC_PROCESSING/
# hierarchy: paths.py -> core -> backend -> webapp -> TRAFFIC_PROCESSING
BASE_DIR: Path = Path(__file__).resolve().parents[3]
# BASE_DIR = .../ITS/TRAFFIC_PROCESSING

# Project root = .../ITS/
PROJECT_ROOT: Path = BASE_DIR.parent

# Models live both at project root and inside TRAFFIC_PROCESSING/.
# Prefer the inner copy to match legacy behaviour; fall back to outer.
INNER_MODELS = BASE_DIR / "models"
OUTER_MODELS = PROJECT_ROOT / "models"
MODELS_DIR: Path = INNER_MODELS if INNER_MODELS.exists() else OUTER_MODELS

# Test set used by live predictions
DATA_AFTER_SPLIT_DIR: Path = BASE_DIR / "scripts" / "data_after_split"
OUTPUTS_DIR: Path = BASE_DIR / "scripts" / "outputs"

# Assets (logo, backgrounds)
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
BACKGROUND_DIR: Path = ASSETS_DIR / "background"
LOGO_PATH: Path = ASSETS_DIR / "logo" / "image.png"

# Data directory for SQLite DBs (locations.db)
DATA_DIR: Path = BASE_DIR
