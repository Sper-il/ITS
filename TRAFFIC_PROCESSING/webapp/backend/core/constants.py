"""
constants.py. Pure-Python constants shared by backend + frontend.
No Streamlit import. Mirrored from the legacy streamlit_app/data/constants.py
with new route strategy names matching the design tokens.
"""
from __future__ import annotations


# ── LOS colour palette
LOS_COLORS = {
    "A": "#2563eb", "B": "#3b82f6", "C": "#60a5fa",
    "D": "#f97316", "E": "#ef4444", "F": "#b91c1c",
}

# Navigation banner colours
NAV_BANNER_COLORS = {
    "default": "#1565C0",
    "warning": "#E65100",
    "danger":  "#B71C1C",
    "off":     "#1B5E20",
}

# Map marker / overlay colours
MAP_COLORS = {
    "start_marker":  "#22c55e",
    "end_marker":    "#ef4444",
    "current_loc":   "#2563eb",
    "off_route":     "#94a3b8",
    "polyline":      "#2563eb",
    "polyline_alt":  "#3b82f6",
}

# LOS Vietnamese name
LOS_NAMES = {
    "A": "Rất tốt (Tự do)",
    "B": "Tốt (Ổn định)",
    "C": "Ổn định (Trung bình)",
    "D": "Kém (Gần tắc)",
    "E": "Rất kém (Tắc nghẽn)",
    "F": "Quá tải (Đứng im)",
}

# LOS long description
LOS_DESC = {
    "A": "Tốc độ cao, mật độ thấp.",
    "B": "Dòng chảy tự do đến bình thường.",
    "C": "Dòng chảy ổn định.",
    "D": "Gần bão hòa. Tốc độ bắt đầu giảm.",
    "E": "Kẹt xe. Tốc độ thấp, dừng chờ.",
    "F": "Tắc nghẽn nghiêm trọng. Dừng hoàn toàn.",
}

# LOS advices (English + emoji-free middots)
LOS_ADVICE = {
    "A": ("Free flow · high speed, no friction.",        "#10b981"),
    "B": ("Stable flow · cruise at design speed.",       "#3b82f6"),
    "C": ("Dense · keep a safe following distance.",     "#60a5fa"),
    "D": ("Near saturation · prepare to slow down.",     "#f59e0b"),
    "E": ("Heavy congestion · consider an alternative.", "#ef4444"),
    "F": ("Gridlock · avoid this segment if possible.",  "#b91c1c"),
}

# Navigation thresholds (metres)
OFF_ROUTE_THRESH_M = 30.0
WAYPOINT_ADVANCE_M = 50.0
ARRIVAL_THRESH_M = 30.0
GPS_DEFAULT_ACCURACY_M = 30.0

# Vehicle profiles
VEHICLE_PROFILES = {
    "car":       {"name": "Car",       "max_velocity_kmh": 50, "highway_filter": None,        "los_weight_multiplier": 1.0},
    "motorbike": {"name": "Motorbike", "max_velocity_kmh": 40, "highway_filter": None,        "los_weight_multiplier": 0.9},
    "bicycle":   {"name": "Bicycle",   "max_velocity_kmh": 18, "highway_filter": "no_motorway","los_weight_multiplier": 1.2},
    "foot":      {"name": "On foot",   "max_velocity_kmh":  5, "highway_filter": "foot_only", "los_weight_multiplier": 1.0},
}

# Route strategy colours (used in route comparison cards)
ROUTE_COLORS = {
    "least_congested": "#2563eb",
    "fastest":         "#f59e0b",
    "shortest":        "#10b981",
}

ROUTE_STRATEGY_NAMES = {
    "least_congested": "Ít kẹt nhất",
    "fastest":         "Nhanh nhất",
    "shortest":        "Ngắn nhất",
}

# Waypoint constants
MAX_WAYPOINTS = 5
WAYPOINT_COLOR = "#f97316"

# History and favorites limits
HISTORY_MAX_ENTRIES = 50
FAVORITES_MAX_ENTRIES = 30

# GPX export template (GPX 1.1)
GPX_EXPORT_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<gpx version="1.1" creator="ITS Traffic Dashboard"\n'
    '     xmlns="http://www.topografix.com/GPX/1/1">\n'
    "  <metadata>\n"
    "    <name>ITS Traffic Route</name>\n"
    "  </metadata>\n"
    "</gpx>"
)

NAV_OFF_ROUTE_DEBOUNCE_COUNT = 3

# ML validation metrics (mirrored from training_metrics.json fallback)
DEFAULT_METRICS = {
    "val_accuracy":      0.751,
    "val_macro_f1":      0.677,
    "cv_accuracy_mean":  0.907,
}
