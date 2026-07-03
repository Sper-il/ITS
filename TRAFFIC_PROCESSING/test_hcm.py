"""Test HCM formula v3 — correct speed ratio handling."""
import sys, math
sys.path.insert(0, "webapp/backend")

def _road_type(max_velocity):
    if max_velocity >= 80: return "highway"
    elif max_velocity >= 50: return "urban"
    return "local"

def _probs_from_speed(speed_ratio: float, road: str) -> dict[str, float]:
    """
    Map speed_ratio to LOS probability distribution.

    HCM urban LOS by speed_ratio (actual_speed / free_flow_speed):
      A: > 0.833  (ratio 0.833–1.0)
      B: 0.667–0.833
      C: 0.500–0.667
      D: 0.400–0.500
      E: 0.333–0.400
      F: < 0.333
    """
    los_letters = ["A", "B", "C", "D", "E", "F"]
    # Speed ratio boundaries for each LOS (lower bound inclusive, upper exclusive)
    # A: [0.833, 1.0], B: [0.667, 0.833), C: [0.500, 0.667), D: [0.400, 0.500), E: [0.333, 0.400), F: [0.000, 0.333)
    # Tighten for local roads
    thresh = {
        "urban":  [1.0, 0.833, 0.667, 0.500, 0.400, 0.333, 0.000],
        "local":  [1.0, 0.80,  0.65,  0.50,  0.35,  0.25,  0.000],
    }.get(road, [1.0, 0.833, 0.667, 0.500, 0.400, 0.333, 0.000])

    probs = {l: 0.0 for l in los_letters}

    # Find which band the speed_ratio falls into
    found = False
    for i in range(len(los_letters)):
        lo = thresh[i + 1]   # lower bound
        hi = thresh[i]       # upper bound
        if lo <= speed_ratio <= hi:
            # Within this LOS band
            center = (lo + hi) / 2
            half_w = (hi - lo) / 2
            if half_w > 0:
                z = abs(speed_ratio - center) / half_w
                probs[los_letters[i]] = max(0.01, 1.0 - z * 0.5)
                # Share some probability with adjacent bands
                if i > 0:
                    adj_center = (lo + thresh[i]) / 2  # upper adjacent
                    adj_half = (thresh[i] - thresh[i+1]) / 2
                    if adj_half > 0:
                        z_adj = abs(speed_ratio - adj_center) / adj_half
                        probs[los_letters[i-1]] = max(0.01, 0.4 * (1.0 - z_adj * 0.5))
                if i < len(los_letters) - 1:
                    adj_lo = thresh[i + 2]
                    adj_hi = lo
                    adj_center = (adj_lo + adj_hi) / 2
                    adj_half = (adj_hi - adj_lo) / 2
                    if adj_half > 0:
                        z_adj = abs(speed_ratio - adj_center) / adj_half
                        probs[los_letters[i+1]] = max(0.01, 0.4 * (1.0 - z_adj * 0.5))
            found = True
            break

    if not found:
        # Speed ratio outside all ranges
        if speed_ratio > thresh[0]:  # > 1.0
            probs["A"] = 0.8
            probs["B"] = 0.2
        elif speed_ratio < thresh[-1]:  # < lower F bound
            probs["F"] = 0.8
            probs["E"] = 0.2

    return probs


def _hcm_los(length, max_velocity, vc_ratio, hour, is_weekend, is_rush):
    vc = max(0.0, min(float(vc_ratio), 4.0))
    ffs = float(max_velocity)
    road = _road_type(ffs)
    length_m = float(length)

    # Rush factor: multiply effective vc
    rush_mult = 1.0
    if is_weekend:
        rush_mult = 0.70
    elif hour in range(7, 10):
        rush_mult = 1.25
    elif hour in range(16, 20):
        rush_mult = 1.40
    elif hour in range(11, 14):
        rush_mult = 1.05

    # Capacity
    cap_base = {"highway": 2200, "urban": 1800, "local": 1400}[road]
    lanes = 4 if length_m >= 2000 else 3 if length_m >= 500 else 2 if length_m >= 100 else 1
    total_cap = cap_base * lanes

    # Effective v/c after rush adjustment
    adjusted_vc = vc * rush_mult
    effective_vc = min(adjusted_vc, total_cap / max(cap_base, 1) if lanes > 0 else 4.0)

    if road == "highway":
        # HCM Freeway: LOS by density = adjusted_vc * 40 (pc/mi/ln equiv)
        # Thresholds: A<11, B<18, C<26, D<35, E<45, F>=45
        density = adjusted_vc * 40
        bounds = [0, 11, 18, 26, 35, 45, 100]
        los_map = ["A", "B", "C", "D", "E", "F"]
        probs = {l: 0.0 for l in los_map}
        for i, letter in enumerate(los_map):
            lo, hi = bounds[i], bounds[i + 1]
            if lo <= density <= hi:
                mid = (lo + hi) / 2
                half_w = max((hi - lo) / 2, 1)
                z = abs(density - mid) / half_w
                probs[letter] = max(0.01, 1.0 - z * 0.5)
        los = max(probs, key=lambda k: probs[k])

    else:  # urban or local
        # BPR function: speed_ratio = 1 / (1 + 0.15 * vc^power)
        power = 3.0 if road == "local" else 3.5
        # Apply lane adjustment: more lanes = more capacity = better LOS for same vc
        lane_factor = min(lanes / 2.0, 1.5)  # 1-2 lane segments get better flow
        vc_eff = max(0, min(adjusted_vc / lane_factor, 3.0))
        speed_ratio = 1.0 / (1.0 + 0.15 * (vc_eff ** power))

        probs = _probs_from_speed(speed_ratio, road)
        los = max(probs, key=lambda k: probs[k])

    # Normalize
    total = sum(probs.values())
    probs = {k: v / total for k, v in probs.items()}
    conf = probs.get(los, 0.5)

    return los, conf, probs


tests = [
    ("Highway free flow",  100, 120, 0.15,  3, False, False),
    ("Highway light",      200, 100, 0.40, 10, False, False),
    ("Highway dense",      500,  90, 0.70, 17, False, True),
    ("Highway near sat",   500,  80, 0.90, 18, False, True),
    ("Highway over cap",   500,  80, 1.20, 18, False, True),
    ("Urban free flow",    200,  60, 0.25, 12, False, False),
    ("Urban moderate",      300,  50, 0.60, 12, False, False),
    ("Urban heavy",        500,  40, 0.90, 17, False, True),
    ("Urban saturation",   800,  40, 1.20, 18, False, True),
    ("Urban gridlock",    1000,  30, 1.50, 18, False, True),
    ("Local good",        100,  30, 0.30, 14, True,  False),
    ("Local congested",    200,  30, 0.90, 18, False, True),
    ("Local free flow",    100,  50, 0.20, 10, False, False),
]

print("HCM v3 predictions:")
unique = set()
for desc, *args in tests:
    pred, conf, proba = _hcm_los(*args)
    unique.add(pred)
    top3 = sorted(proba.items(), key=lambda x: -x[1])[:3]
    print(f"  {desc:25s}: {pred} (conf={conf:.3f}) | " +
          ", ".join(f"{k}={v:.3f}" for k, v in top3))

print(f"\nUnique: {sorted(unique)}")
print("PASS!" if len(unique) >= 4 else "NEEDS IMPROVEMENT")
