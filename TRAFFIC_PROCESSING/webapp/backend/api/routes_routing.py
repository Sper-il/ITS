"""
routes_routing.py. JSON API for the Routing tab.

GET  /api/route/presets              → list of HCM landmarks
GET  /api/route/graph/stats          → {nodes, edges}
POST /api/route/find                 → body {start_lat, start_lon, end_lat, end_lon, vehicle}
POST /api/route/gps-update           → body {lat, lon, accuracy} → snap + remaining distance
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..core.presets import HCM_PRESETS
from ..core.routing_engine import (
    find_all_paths_between,
    graph_stats,
)
from ..core.routing_math import format_distance_km, haversine_m


bp = Blueprint("route", __name__, url_prefix="/api/route")


@bp.get("/presets")
def presets():
    out = []
    for label, lat, lon in HCM_PRESETS:
        is_header = lat is None and lon is None
        out.append({
            "label":     label,
            "lat":       lat,
            "lon":       lon,
            "is_header": is_header,
        })
    return jsonify({"presets": out})


@bp.get("/graph/stats")
def graph_stats_endpoint():
    try:
        stats = graph_stats()
        ok = stats["nodes"] > 0 and stats["edges"] > 0
    except Exception as ex:
        return jsonify({
            "nodes": 0, "edges": 0,
            "ok": False,
            "error": f"{type(ex).__name__}: {str(ex)[:140]}",
        })
    return jsonify({**stats, "ok": ok})


@bp.post("/find")
def find_route():
    body = request.get_json(silent=True) or {}
    try:
        s_lat = float(body["start_lat"])
        s_lon = float(body["start_lon"])
        e_lon = float(body["end_lon"])
        vehicle = str(body.get("vehicle", "car"))
        predict_hour = body.get("predict_hour")
        if predict_hour is not None:
            predict_hour = int(predict_hour)
        avoid_tolls = bool(body.get("avoid_tolls", False))
        avoid_ferries = bool(body.get("avoid_ferries", False))
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "missing or invalid parameters"}), 400

    try:
        routes = find_all_paths_between(
            s_lat, s_lon, e_lat, e_lon, 
            vehicle=vehicle,
            predict_hour=predict_hour,
            avoid_tolls=avoid_tolls,
            avoid_ferries=avoid_ferries
        )
    except Exception as ex:
        return jsonify({"error": f"{type(ex).__name__}: {str(ex)[:200]}"}), 500

    if not routes:
        return jsonify({
            "routes": [],
            "message": "Đồ thị hiện tại chưa được kết nối đầy đủ giữa hai điểm. Hãy thử hai địa điểm gần nhau hơn hoặc build lại cache graph.",
        })

    return jsonify({
        "routes": routes,
        "summary": {
            "total": len(routes),
            "best_los": routes[0],   # least congestion comes first
        },
    })


@bp.post("/gps-update")
def gps_update():
    """Snap a free GPS fix to the road + return remaining distance to destination.

    Used by the real-time Navigation Mode on the front-end.
    """
    body = request.get_json(silent=True) or {}
    try:
        lat = float(body["lat"])
        lon = float(body["lon"])
        dst_lat = float(body.get("dest_lat", 0))
        dst_lon = float(body.get("dest_lon", 0))
        accuracy = float(body.get("accuracy", 30.0))
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "missing fields"}), 400

    from ..core.routing_engine import find_nearest_node
    node = find_nearest_node(lat, lon)
    remaining_m = (
        haversine_m(lat, lon, dst_lat, dst_lon) if dst_lat and dst_lon else 0.0
    )
    return jsonify({
        "nearest_node": node,
        "remaining_m":  round(remaining_m, 1),
        "remaining_display": format_distance_km(remaining_m),
        "accuracy":     accuracy,
    })


@bp.post("/multi-leg")
def multi_leg_route():
    """Find a route through an ordered list of (lat, lon) waypoints.

    Body:
        {
          "waypoints": [
            {"lat": 10.78, "lon": 106.69, "label": "Start"},
            {"lat": 10.79, "lon": 106.71, "label": "Stop 1"},
            {"lat": 10.80, "lon": 106.72, "label": "End"}
          ],
          "vehicle": "car"
        }

    Response:
        { "legs": [ RouteResult, ... ], "total_distance_m": N, "total_travel_time_s": N }
    """
    body = request.get_json(silent=True) or {}
    wps_raw = body.get("waypoints", [])
    if not isinstance(wps_raw, list) or len(wps_raw) < 2:
        return jsonify({"error": "need at least 2 waypoints"}), 400

    try:
        waypoints: list[tuple[float, float]] = []
        for w in wps_raw:
            waypoints.append((float(w["lat"]), float(w["lon"])))
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "invalid waypoint coordinates"}), 400

    vehicle = str(body.get("vehicle", "car"))
    predict_hour = body.get("predict_hour")
    if predict_hour is not None:
        try:
            predict_hour = int(predict_hour)
        except ValueError:
            predict_hour = None
    avoid_tolls = bool(body.get("avoid_tolls", False))
    avoid_ferries = bool(body.get("avoid_ferries", False))

    try:
        from ..core.routing_engine import _load_graph, find_all_paths_between, graph_stats  # noqa
        from ..core.graph_bridge import ensure_reachable, get_routing_graph_and_evaluator
        from scripts.routing.routing_engine import (
            find_all_paths as _legacy_find,
            format_travel_time as _format_tt,
        )
        G = _load_graph()
        from ..core.routing_engine import find_nearest_node
        s_node = find_nearest_node(waypoints[0][0], waypoints[0][1])
        t_node = find_nearest_node(waypoints[-1][0], waypoints[-1][1])
        s_node, t_node = ensure_reachable(G, s_node, t_node)

        G_base, get_weight_func, evaluate_edge_dict = get_routing_graph_and_evaluator(
            G, 
            vehicle,
            predict_hour=predict_hour,
            avoid_tolls=avoid_tolls,
            avoid_ferries=avoid_ferries
        )

        from ..core.constants import ROUTE_STRATEGY_NAMES
        strategies = [
            (ROUTE_STRATEGY_NAMES["least_congested"], get_weight_func("los_weight")),
        ]

        legs_out = []
        total_dist = 0.0
        total_time = 0.0

        for i in range(len(waypoints) - 1):
            src_coord = waypoints[i]
            dst_coord = waypoints[i + 1]
            s_n = find_nearest_node(src_coord[0], src_coord[1])
            t_n = find_nearest_node(dst_coord[0], dst_coord[1])
            if s_n is None or t_n is None:
                return jsonify({"error": f"cannot snap waypoint {i} or {i+1}"}), 400
            s_n, t_n = ensure_reachable(G_base, s_n, t_n)

            results = _legacy_find(
                G_base, s_n, t_n,
                start_coord=src_coord if i == 0 else None,
                end_coord=dst_coord if i == len(waypoints) - 2 else None,
                strategies=strategies,
                edge_evaluator=evaluate_edge_dict,
            )
            if not results:
                return jsonify({
                    "error": f"no route for leg {i} → {i+1}",
                    "leg": i,
                }), 404

            r = results[0]
            total_dist += r.total_distance_m
            total_time += r.total_travel_time_s

            legs_out.append({
                "leg_index":           i,
                "from_coord":          list(src_coord),
                "to_coord":            list(dst_coord),
                "strategy":            r.strategy,
                "total_distance_m":    r.total_distance_m,
                "total_distance_display": format_distance_km(r.total_distance_m),
                "total_travel_time_s": r.total_travel_time_s,
                "total_travel_time_str": _format_tt(r.total_travel_time_s),
                "geometry":            [list(p) for p in r.geometry_route],
                "edges": [
                    {
                        "from":       e["from"],
                        "to":         e["to"],
                        "length_m":   e["length_m"],
                        "los":        e["los"],
                        "street":     e.get("street_name") or e.get("street", ""),
                        "travel_time_s": e["travel_time_s"],
                    } for e in r.edges
                ],
            })

        return jsonify({
            "legs": legs_out,
            "total_distance_m":     total_dist,
            "total_distance_display": format_distance_km(total_dist),
            "total_travel_time_s":  total_time,
            "total_travel_time_str": _format_tt(total_time),
            "waypoint_count":       len(waypoints),
            "vehicle":              vehicle,
        })
    except Exception as ex:
        return jsonify({"error": f"{type(ex).__name__}: {str(ex)[:200]}"}), 500


@bp.get("/export-gpx")
def export_gpx_route():
    """Re-build a GPX file from start/end coords and stream it back.

    Query params: start_lat, start_lon, end_lat, end_lon, vehicle (default car).
    """
    from flask import Response
    try:
        s_lat = float(request.args["start_lat"])
        s_lon = float(request.args["start_lon"])
        e_lat = float(request.args["end_lat"])
        e_lon = float(request.args["end_lon"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "missing query params"}), 400

    vehicle = request.args.get("vehicle", "car")

    try:
        routes = find_all_paths_between(s_lat, s_lon, e_lat, e_lon, vehicle=vehicle)
    except Exception as ex:
        return jsonify({"error": f"{type(ex).__name__}: {str(ex)[:200]}"}), 500

    if not routes:
        return jsonify({"error": "no route found"}), 404

    visible = [r for r in routes if r["strategy"] != "Ngắn nhất"]
    sel = visible[0] if visible else routes[0]
    geometry = sel.get("geometry") or []
    if not geometry:
        return jsonify({"error": "empty geometry"}), 500

    name = f"ITS_Route_{s_lat:.4f}_{s_lon:.4f}_to_{e_lat:.4f}_{e_lon:.4f}"
    pts = "\n".join(
        f'      <trkpt lat="{la}" lon="{lo}"></trkpt>'
        for la, lo in geometry
    )
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<gpx version="1.1" creator="ITS Traffic Dashboard" '
        f'xmlns="http://www.topografix.com/GPX/1/1">\n'
        f'  <metadata>\n'
        f'    <name>{name}</name>\n'
        f'    <time>{__import__("datetime").datetime.utcnow().isoformat()}Z</time>\n'
        f'  </metadata>\n'
        f'  <trk>\n'
        f'    <name>{name}</name>\n'
        f'    <trkseg>\n{pts}\n    </trkseg>\n'
        f'  </trk>\n'
        f'</gpx>'
    )
    return Response(xml, mimetype="application/gpx+xml", headers={
        "Content-Disposition": f'attachment; filename="{name}.gpx"',
    })
