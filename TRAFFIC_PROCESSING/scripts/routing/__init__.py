import sys, os
from pathlib import Path

log_path = r"c:\Users\Admin\Downloads\ITS\_routing_import.log"
_scripts_root = Path(__file__).resolve().parent  # TRAFFIC_PROCESSING/scripts/routing/
_package_root = _scripts_root.parent  # TRAFFIC_PROCESSING/

with open(log_path, "w", encoding="utf-8") as f:
    f.write(f"[routing/__init__.py] sys.path[:3] = {sys.path[:3]}\n")
    f.write(f"[routing/__init__.py] _package_root = {_package_root}\n")
    f.write(f"[routing/__init__.py] _scripts_root = {_scripts_root}\n")

if str(_package_root) not in sys.path:
    sys.path.insert(0, str(_package_root))
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[routing/__init__.py] added _package_root to sys.path\n")
