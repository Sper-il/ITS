"""
routing_math.py. Pure geometric helpers (haversine, bearings, maneuvers).

Refactored from streamlit_app/lib/routing_math.py: removed ``streamlit`` import path,
kept all math identical, exposed ``format_travel_time`` for the API.
"""
from __future__ import annotations

import math
from typing import Optional


# ── Bearings & distances ──────────────────────────────────────────────
def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing (degrees, 0=N, 90=E) between two WGS-84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Metres between two WGS-84 points."""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def segment_point_dist(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-12:
        return haversine_m(px, py, ax, ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return haversine_m(px, py, ax + t * dx, ay + t * dy)


def perp_dist_to_polyline(lat: float, lon: float, waypoints: list) -> float:
    min_dist = float("inf")
    for i in range(len(waypoints) - 1):
        p1, p2 = waypoints[i], waypoints[i + 1]
        d = segment_point_dist(lat, lon, p1[0], p1[1], p2[0], p2[1])
        if d < min_dist:
            min_dist = d
    return min_dist


# ── Turn-by-turn ───────────────────────────────────────────────────────
def maneuver_for_edge(prev_edge, edge, next_edge) -> tuple[str, str]:
    if edge is None:
        return ("icon.start", "Điểm xuất phát")
    if next_edge is None:
        return ("icon.arrive", "Đến nơi")
    e1 = edge
    e2 = next_edge
    b_out = bearing_deg(
        e1.get("lat2", 0), e1.get("lon2", 0),
        e2.get("lat1", 0), e2.get("lon2", 0),
    )
    b_in = bearing_deg(
        e1.get("lat1", 0), e1.get("lon1", 0),
        e1.get("lat2", 0), e1.get("lon2", 0),
    )
    diff = ((b_out - b_in + 540) % 360) - 180
    ad = abs(diff)
    if ad < 18:
        return ("icon.straight", "Đi thẳng")
    if ad < 60:
        if diff > 0:
            return ("icon.slight-right", "Rẽ nhẹ phải")
        return ("icon.slight-left", "Rẽ nhẹ trái")
    if ad < 120:
        if diff > 0:
            return ("icon.right", "Rẽ phải")
        return ("icon.left", "Trái")
    if diff > 0:
        return ("icon.uturn-right", "Quay đầu phải")
    return ("icon.uturn-left", "Quay đầu trái")


def build_nav_waypoints_and_instrs(route) -> tuple[list, list]:
    """Extract (lat,lon) list + instruction dicts from a route."""
    waypoints: list = []
    instrs: list = []
    if not route or not getattr(route, "edges", None):
        return [], []
    for edge in route.edges:
        a = edge.get("lat1") or edge.get("lat2", 0)
        b = edge.get("lon1") or edge.get("lon2", 0)
        if not (a and b):
            continue
        waypoints.append((a, b))
        instrs.append({
            "street": edge.get("street_name") or edge.get("street", "Không rõ tên đường"),
            "length_m": edge.get("length_m", 0),
            "travel_time_s": edge.get("travel_time_s", 0),
            "los": edge.get("los", "B"),
        })
    return waypoints, instrs


# ── Time formatting ───────────────────────────────────────────────────
def format_travel_time(seconds: float) -> str:
    """Xh Ym string, used in edge popups + ETA display."""
    if seconds is None or seconds <= 0:
        return "0m"
    m_total = int(seconds // 60)
    h = m_total // 60
    m = m_total % 60
    if h == 0:
        return f"{m}m"
    return f"{h}h {m}m"


def format_distance_km(metres: float) -> str:
    if metres >= 1000:
        return f"{metres / 1000:.1f} km"
    return f"{int(metres)} m"
