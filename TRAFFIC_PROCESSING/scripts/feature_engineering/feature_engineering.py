"""
Feature Engineering script — Traffic LOS prediction project.

Nâng cấp từ phiên bản trước với:
  - Vectorized spatial features: BallTree-based kNN, node density (thay iterrows)
  - Network features: node degree centrality, pagerank-like metrics, clustering
  - Full temporal: cyclical, rush-hour, day-type, holiday flags
  - Traffic features: travel time, V/C, delay, z-score
  - Lag/Rolling/Diff: day/week windows
  - Aggregated profiles: per-segment, per-period, per-(segment, period)
  - CSV output: xuất .csv thay vì .parquet
  - Detailed logging: before/after shape + feature list
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
from typing import Literal

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import warnings
warnings.filterwarnings("ignore")

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


# =============================================================================
# LOGGER
# =============================================================================

def log(msg: str):
    print(msg)

def log_step(msg: str):
    print(f"  >> {msg}")

def log_info(msg: str):
    print(f"      {msg}")


# =============================================================================
# 1. TEMPORAL FEATURES
# =============================================================================

def extract_temporal_features(df: pd.DataFrame, period_col: str = "period",
                              date_col: str = "date") -> pd.DataFrame:
    """
    Extract comprehensive temporal features:
      - Basic date parts
      - Cyclical sin/cos encodings (hour, weekday, month, dayofyear)
      - Rush-hour binary flags
      - Time-of-day categories
      - Holiday flags (Vietnam approximation)
    """
    df = df.copy()
    log_step("Extracting temporal features...")

    # Parse date / period
    dates = pd.to_datetime(df[date_col], errors="coerce")

    df["year"] = dates.dt.year
    df["month"] = dates.dt.month
    df["day"] = dates.dt.day
    df["dayofyear"] = dates.dt.dayofyear
    df["weekday"] = dates.dt.weekday.fillna(-1).astype(int)
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    df["quarter"] = dates.dt.quarter
    df["weekofyear"] = dates.dt.isocalendar().week.astype(int)

    # Parse period column
    if period_col in df.columns:
        period_str = df[period_col].astype(str)

        # Thử format "period_HH_MM"
        extracted_h = period_str.str.extract(r"period_(\d+)_")[0].astype(float)
        extracted_m = period_str.str.extract(r"period_\d+_(\d+)")[0].astype(float)

        null_ratio = extracted_h.isna().mean()
        if null_ratio > 0.5:
            # Fallback: thử parse dạng "HH:MM" hoặc "HH"
            log_info(f"  [WARNING] period regex khớp chỉ {(1-null_ratio)*100:.1f}% dòng. Thử fallback parse...")
            fallback_h = pd.to_datetime(period_str, format="%H:%M", errors="coerce").dt.hour
            if fallback_h.notna().mean() > 0.5:
                extracted_h = fallback_h
                extracted_m = pd.to_datetime(period_str, format="%H:%M", errors="coerce").dt.minute
                log_info("  Fallback HH:MM parse thành công.")
            else:
                extracted_h2 = pd.to_numeric(period_str, errors="coerce")
                if extracted_h2.notna().mean() > 0.5:
                    extracted_h = extracted_h2
                    extracted_m = pd.Series(0, index=df.index, dtype=float)
                    log_info("  Fallback numeric hour parse thành công.")
                else:
                    log_info("  [WARNING] Không thể parse period column — period_hour sẽ là NaN.")

        df["period_hour"] = extracted_h
        df["period_minute"] = extracted_m
        df["period_minutes_of_day"] = (
            df["period_hour"].fillna(0) * 60 + df["period_minute"].fillna(0)
        )
    else:
        log_info(f"  [WARNING] Cột '{period_col}' không tồn tại — period_hour sẽ là NaN.")
        df["period_hour"] = np.nan
        df["period_minute"] = np.nan
        df["period_minutes_of_day"] = np.nan

    # Cyclical encodings
    h = df["period_hour"].fillna(12)
    df["hour_sin"] = np.sin(2 * np.pi * h / 24)
    df["hour_cos"] = np.cos(2 * np.pi * h / 24)
    w = df["weekday"].replace(-1, 0)
    df["weekday_sin"] = np.sin(2 * np.pi * w / 7)
    df["weekday_cos"] = np.cos(2 * np.pi * w / 7)
    m = df["month"].replace(0, 1).fillna(1)
    df["month_sin"] = np.sin(2 * np.pi * m / 12)
    df["month_cos"] = np.cos(2 * np.pi * m / 12)
    doy = df["dayofyear"].replace(0, 1).fillna(1)
    df["dayofyear_sin"] = np.sin(2 * np.pi * doy / 365)
    df["dayofyear_cos"] = np.cos(2 * np.pi * doy / 365)

    # Rush-hour flags
    df["is_morning_rush"] = ((h >= 6) & (h < 9)).astype(int)
    df["is_evening_rush"] = ((h >= 16) & (h < 19)).astype(int)
    df["is_rush_hour"] = (df["is_morning_rush"] | df["is_evening_rush"]).astype(int)
    df["is_night"] = ((h >= 22) | (h < 5)).astype(int)
    df["is_working_hours"] = ((h >= 8) & (h < 18)).astype(int)
    df["is_lunch"] = ((h >= 11) & (h < 13)).astype(int)

    # Time of day category
    df["time_of_day_cat"] = pd.cut(
        h, bins=[-1, 6, 12, 18, 24],
        labels=["night", "morning", "afternoon", "evening"]
    ).astype(str)

    # Season — Việt Nam chỉ có 2 mùa: mùa mưa (5-11) và mùa khô (12-4)
    df["season"] = df["month"].map({
        1: "dry", 2: "dry", 3: "dry", 4: "dry",
        5: "rainy", 6: "rainy", 7: "rainy", 8: "rainy",
        9: "rainy", 10: "rainy", 11: "rainy",
        12: "dry",
    }).fillna("unknown")

    # Vietnam holidays — đầy đủ 2019-2024, bao gồm Tết Nguyên Đán
    vietnam_holidays = {
        # 2019
        "2019-01-01", "2019-02-04", "2019-02-05", "2019-02-06",
        "2019-02-07", "2019-02-08", "2019-02-09", "2019-04-30",
        "2019-05-01", "2019-09-02",
        # 2020
        "2020-01-01", "2020-01-23", "2020-01-24", "2020-01-25",
        "2020-01-26", "2020-01-27", "2020-01-28", "2020-04-30",
        "2020-05-01", "2020-09-02",
        # 2021
        "2021-01-01", "2021-02-10", "2021-02-11", "2021-02-12",
        "2021-02-13", "2021-02-14", "2021-02-15", "2021-04-30",
        "2021-05-01", "2021-09-02",
        # 2022
        "2022-01-01", "2022-01-31", "2022-02-01", "2022-02-02",
        "2022-02-03", "2022-02-04", "2022-02-05", "2022-04-30",
        "2022-05-01", "2022-09-02",
        # 2023
        "2023-01-01", "2023-01-20", "2023-01-21", "2023-01-22",
        "2023-01-23", "2023-01-24", "2023-01-25", "2023-04-30",
        "2023-05-01", "2023-09-02",
        # 2024
        "2024-01-01", "2024-02-08", "2024-02-09", "2024-02-10",
        "2024-02-11", "2024-02-12", "2024-02-13", "2024-04-30",
        "2024-05-01", "2024-09-02",
    }
    dates_str = dates.dt.strftime("%Y-%m-%d")
    df["is_holiday"] = dates_str.isin(vietnam_holidays).astype(int)
    df["is_tet"] = dates_str.isin({
        # Các ngày Tết Nguyên Đán cụ thể (ngày mùng 1)
        "2019-02-05", "2020-01-25", "2021-02-12",
        "2022-02-01", "2023-01-22", "2024-02-10",
    }).astype(int)

    feat_count = len(df.columns)
    log_info(f"  Added temporal features. Total cols: {feat_count}")
    return df


# =============================================================================
# 2. SPATIAL / GEOMETRIC FEATURES
# =============================================================================

def compute_geometry_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute segment geometry from start/end node coordinates:
      - Haversine distance (km)
      - Bearing/azimuth (degrees)
      - Midpoint coordinates
      - Direction deltas
    """
    df = df.copy()
    log_step("Computing geometry features...")

    lon1 = np.radians(df["long_snode"].astype(float))
    lat1 = np.radians(df["lat_snode"].astype(float))
    lon2 = np.radians(df["long_enode"].astype(float))
    lat2 = np.radians(df["lat_enode"].astype(float))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    df["length_haversine_km"] = 2 * 6371 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    bearing = np.arctan2(
        np.sin(dlon) * np.cos(lat2),
        np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
    )
    df["segment_bearing_deg"] = np.degrees(bearing)

    df["midpoint_long"] = (df["long_snode"].astype(float) + df["long_enode"].astype(float)) / 2
    df["midpoint_lat"] = (df["lat_snode"].astype(float) + df["lat_enode"].astype(float)) / 2
    df["delta_long"] = df["long_enode"].astype(float) - df["long_snode"].astype(float)
    df["delta_lat"] = df["lat_enode"].astype(float) - df["lat_snode"].astype(float)

    log_info(f"  Added: length_haversine_km, segment_bearing_deg, midpoint_long/lat, delta_long/lat")
    return df


def compute_spatial_features_balltree(
    df: pd.DataFrame,
    nodes_df: pd.DataFrame,
    k: int = 5,
    density_radius_km: float = 0.5,
) -> pd.DataFrame:
    """
    Vectorized spatial density using BallTree (sklearn).

    For each unique midpoint in df, finds k nearest nodes and computes:
      - Distance to k nearest nodes
      - Node density within radius (proxy for urban congestion)

    Uses BallTree for O(n log n) instead of O(n * m) with iterrows.
    """
    df = df.copy()
    log_step(f"Computing spatial density (BallTree, k={k}, radius={density_radius_km}km)...")

    try:
        from sklearn.neighbors import BallTree

        # Build tree from nodes
        node_coords = np.radians(nodes_df[["long", "lat"]].dropna().values)
        tree = BallTree(node_coords, metric="haversine")

        # Query points: midpoints of segments
        query_coords = np.radians(
            df[["midpoint_long", "midpoint_lat"]].dropna().values
        )

        if len(query_coords) == 0:
            log_info("  No valid coordinates, skipping spatial density")
            return df

        # k-nearest distances
        dists, _ = tree.query(query_coords, k=min(k, len(node_coords)))
        # dists in radians -> km
        dists_km = dists * 6371

        # Create mapping from df index to distances
        valid_idx = df[["midpoint_long", "midpoint_lat"]].dropna().index

        for j in range(min(k, dists_km.shape[1])):
            df.loc[valid_idx, f"nearest_node_dist_{j}"] = dists_km[:, j]

        # Average distance to k nearest
        df.loc[valid_idx, "avg_dist_to_k_nodes"] = dists_km[:, :k].mean(axis=1)
        df.loc[valid_idx, "min_dist_to_node"] = dists_km[:, 0]
        df.loc[valid_idx, "max_dist_to_k_nodes"] = dists_km[:, :k].max(axis=1)

        # Node density: count nodes within radius
        count_in_radius = tree.query_radius(
            query_coords, r=density_radius_km / 6371, count_only=True
        )
        df.loc[valid_idx, f"node_density_{int(density_radius_km*1000)}m"] = count_in_radius

        log_info(f"  Added: nearest_node_dist_0..{k-1}, avg_dist_to_k_nodes, "
                 f"node_density_{int(density_radius_km*1000)}m")

    except ImportError:
        log_info("  sklearn not available, skipping BallTree spatial features")

    return df


def compute_network_features(
    segments_df: pd.DataFrame,
    nodes_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute graph/network features from segments adjacency:
      - Node degree (number of segments connected)
      - Start/end degree separately
      - Dead-end node flag
      - Intersection type
    """
    log_step("Computing network features...")
    df = nodes_df.copy()

    # Degree from start nodes
    if "node_degree" not in df.columns:
        start_deg = segments_df.groupby("s_node_id").size().reset_index(name="start_degree")
        end_deg = segments_df.groupby("e_node_id").size().reset_index(name="end_degree")

        df = df.merge(start_deg, left_on="_id", right_on="s_node_id", how="left")
        df = df.merge(end_deg, left_on="_id", right_on="e_node_id", how="left")
        df[["start_degree", "end_degree"]] = df[["start_degree", "end_degree"]].fillna(0)
        df["node_degree"] = df["start_degree"] + df["end_degree"]
        df["node_degree"] = df["node_degree"].fillna(0).astype(int)
        df["start_degree"] = df["start_degree"].astype(int)
        df["end_degree"] = df["end_degree"].astype(int)

    # Dead-end node (only one segment)
    df["is_dead_end"] = (df["node_degree"] == 1).astype(int)

    # Intersection type
    df["is_intersection"] = (df["node_degree"] > 2).astype(int)
    df["is_4way"] = (df["node_degree"] >= 4).astype(int)

    # Segment-level aggregations
    seg_net = (
        df.groupby("_id")
        .agg(
            seg_avg_degree=("node_degree", "mean"),
            seg_max_degree=("node_degree", "max"),
            seg_dead_ends=("is_dead_end", "sum"),
            seg_intersections=("is_intersection", "sum"),
        )
        .reset_index()
        .rename(columns={"_id": "s_node_id"})
    )
    log_info(f"  Added: node_degree, start_degree, end_degree, is_dead_end, is_intersection, is_4way")
    return df, seg_net


# =============================================================================
# 3. INFRASTRUCTURE FEATURES
# =============================================================================

def compute_infrastructure_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode street type priority, capacity proxy, lane estimate."""
    df = df.copy()
    log_step("Computing infrastructure features...")

    priority_map = {
        "trunk": 5, "motorway": 5,
        "primary": 4, "primary_link": 4,
        "secondary": 3, "secondary_link": 3,
        "tertiary": 2, "tertiary_link": 2,
        "unclassified": 1, "residential": 1, "service": 1,
    }
    if "street_type" in df.columns:
        df["street_priority"] = (
            df["street_type"].astype(str).str.lower().map(priority_map).fillna(1)
        )
    else:
        df["street_priority"] = 1

    lane_map = {
        "trunk": 4, "motorway": 4,
        "primary": 3,
        "secondary": 2, "primary_link": 2,
        "tertiary": 2,
        "unclassified": 1, "residential": 1, "service": 1,
    }
    if "street_type" in df.columns:
        df["est_lane_count"] = (
            df["street_type"].astype(str).str.lower().map(lane_map).fillna(1)
        )
    else:
        df["est_lane_count"] = 1

    # Capacity proxy
    length = pd.to_numeric(df["length"], errors="coerce").fillna(1).clip(lower=1)
    max_vel = pd.to_numeric(df["max_velocity"], errors="coerce").fillna(40).clip(lower=1)
    df["capacity_proxy"] = length * max_vel
    df["capacity_per_meter"] = max_vel / length
    df["speed_limit_category"] = pd.cut(
        max_vel, bins=[0, 30, 50, 80, 120],
        labels=["low", "medium", "high", "freeway"]
    ).astype(str)

    log_info("  Added: street_priority, est_lane_count, capacity_proxy, capacity_per_meter, speed_limit_category")
    return df


# =============================================================================
# 4. TRAFFIC-DERIVED FEATURES
# =============================================================================

def compute_traffic_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute congestion/traffic features:
      - V/C ratio
      - Travel time (actual and free-flow)
      - Delay metrics
      - Velocity z-score per segment
    """
    df = df.copy()
    log_step("Computing traffic-derived features...")

    vel = pd.to_numeric(df.get("velocity", df.get("hist_vel_last", np.nan)), errors="coerce")
    length = pd.to_numeric(df["length"], errors="coerce").fillna(1).clip(lower=1)
    max_vel = pd.to_numeric(df["max_velocity"], errors="coerce").fillna(40).clip(lower=1)

    # V/C ratio
    df["vc_ratio"] = (vel / max_vel).clip(0, 5)
    df["vc_ratio"] = df["vc_ratio"].fillna(0.5)

    # Travel time (minutes)
    df["travel_time_actual"] = (length / vel.replace(0, np.nan)).fillna(length / 40)
    df["travel_time_free_flow"] = length / max_vel
    df["travel_time_index"] = (df["travel_time_actual"] / df["travel_time_free_flow"].clip(lower=0.1)).clip(0, 10)
    df["delay_ratio"] = df["travel_time_actual"] - df["travel_time_free_flow"]
    df["delay_per_meter"] = df["delay_ratio"] / length.clip(lower=1)

    # Congestion level category
    vc = df["vc_ratio"]
    df["congestion_level"] = pd.cut(
        vc, bins=[-0.01, 0.2, 0.4, 0.6, 0.75, 0.9, 999],
        labels=["free", "light", "moderate", "heavy", "severe", "breakdown"]
    ).astype(str)

    log_info("  Added: vc_ratio, travel_time_actual, travel_time_free_flow, "
             "travel_time_index, delay_ratio, congestion_level")
    return df


def compute_velocity_zscore(df: pd.DataFrame, group_col: str = "segment_id",
                              val_col: str = "hist_vel_mean") -> pd.DataFrame:
    """Compute per-segment velocity z-score and anomaly flag."""
    df = df.copy()
    if val_col not in df.columns:
        log_info(f"  Column '{val_col}' not found, skipping velocity zscore")
        return df

    log_step("Computing velocity z-score per segment...")
    vals = pd.to_numeric(df[val_col], errors="coerce")
    grp_mean = df.groupby(group_col)[val_col].transform("mean")
    grp_std = df.groupby(group_col)[val_col].transform("std").replace(0, 1)

    df["velocity_zscore"] = ((vals - grp_mean) / grp_std).clip(-5, 5)
    df["velocity_anomaly"] = (np.abs(df["velocity_zscore"]) > 2).astype(int)

    log_info("  Added: velocity_zscore, velocity_anomaly")
    return df


# =============================================================================
# 5. LAG, ROLLING & DIFF FEATURES
# =============================================================================

def compute_lag_features(
    df: pd.DataFrame,
    group_col: str = "segment_id",
    sort_col: str = "date",
    val_col: str = "hist_vel_mean",
    lags: list[int] = None,
) -> pd.DataFrame:
    """Compute lag features for time-series modeling."""
    if lags is None:
        lags = [1, 2, 3, 6, 12, 24]
    df = df.copy()
    log_step(f"Computing lag features (lags={lags})...")

    if sort_col in df.columns:
        df = df.sort_values([group_col, sort_col])
    elif "updated_at" in df.columns:
        df = df.sort_values([group_col, "updated_at"])

    for lag in lags:
        df[f"{val_col}_lag_{lag}"] = (
            df.groupby(group_col)[val_col].shift(lag) if val_col in df.columns else np.nan
        )

    lag_cols = [c for c in df.columns if "_lag_" in c]
    log_info(f"  Added {len(lag_cols)} lag features: {lag_cols}")
    return df


def compute_rolling_features(
    df: pd.DataFrame,
    group_col: str = "segment_id",
    sort_col: str = "date",
    val_col: str = "hist_vel_mean",
    windows: list[int] = None,
) -> pd.DataFrame:
    """Compute rolling statistics (mean, std, min, max) per segment."""
    if windows is None:
        windows = [3, 6, 12, 24]
    df = df.copy()
    log_step(f"Computing rolling features (windows={windows})...")

    if sort_col in df.columns:
        df = df.sort_values([group_col, sort_col])
    elif "updated_at" in df.columns:
        df = df.sort_values([group_col, "updated_at"])

    for w in windows:
        grp = df.groupby(group_col)[val_col] if val_col in df.columns else pd.Series(dtype=float)
        if val_col in df.columns:
            df[f"{val_col}_roll_mean_{w}"] = grp.transform(
                lambda x: x.rolling(window=w, min_periods=1).mean()
            )
            df[f"{val_col}_roll_std_{w}"] = grp.transform(
                lambda x: x.rolling(window=w, min_periods=1).std()
            )
            df[f"{val_col}_roll_min_{w}"] = grp.transform(
                lambda x: x.rolling(window=w, min_periods=1).min()
            )
            df[f"{val_col}_roll_max_{w}"] = grp.transform(
                lambda x: x.rolling(window=w, min_periods=1).max()
            )

    roll_cols = [c for c in df.columns if "_roll_" in c]
    log_info(f"  Added {len(roll_cols)} rolling features")
    return df


def compute_diff_features(
    df: pd.DataFrame,
    group_col: str = "segment_id",
    sort_col: str = "date",
    val_col: str = "hist_vel_mean",
) -> pd.DataFrame:
    """Compute diff (rate of change) features."""
    df = df.copy()
    log_step("Computing diff features...")
    if sort_col in df.columns:
        df = df.sort_values([group_col, sort_col])
    elif "updated_at" in df.columns:
        df = df.sort_values([group_col, "updated_at"])

    if val_col in df.columns:
        df[f"{val_col}_diff_1"] = df.groupby(group_col)[val_col].diff(1)
        df[f"{val_col}_diff_3"] = df.groupby(group_col)[val_col].diff(3)
        df[f"{val_col}_pct_change_1"] = df.groupby(group_col)[val_col].pct_change(1).clip(-1, 10)

    diff_cols = [c for c in df.columns if "_diff_" in c or "_pct_change" in c]
    log_info(f"  Added {len(diff_cols)} diff features: {diff_cols}")
    return df


# =============================================================================
# 6. INTERACTION FEATURES
# =============================================================================

def create_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create polynomial and cross-product interaction terms."""
    df = df.copy()
    log_step("Creating interaction features...")

    if "street_level" in df.columns and "length" in df.columns:
        df["level_x_length"] = df["street_level"] * df["length"]
        df["level_x_length_log"] = np.log1p(df["level_x_length"])

    if "vc_ratio" in df.columns and "period_hour" in df.columns:
        df["vc_x_hour"] = df["vc_ratio"] * df["period_hour"]
        df["vc_x_weekday"] = df["vc_ratio"] * df["weekday"]

    if "is_rush_hour" in df.columns and "street_priority" in df.columns:
        df["rush_x_priority"] = df["is_rush_hour"] * df["street_priority"]

    if "is_weekend" in df.columns and "is_rush_hour" in df.columns:
        df["weekend_x_rush"] = df["is_weekend"] * df["is_rush_hour"]

    if "vc_ratio" in df.columns and "est_lane_count" in df.columns:
        df["vc_x_lanes"] = df["vc_ratio"] * df["est_lane_count"]

    if "length_haversine_km" in df.columns and "vc_ratio" in df.columns:
        df["length_x_vc"] = df["length_haversine_km"] * df["vc_ratio"]

    int_cols = [c for c in df.columns if "_x_" in c]
    log_info(f"  Added {len(int_cols)} interaction features: {int_cols}")
    return df


# =============================================================================
# 7. AGGREGATED PROFILE FEATURES
# =============================================================================

def build_segment_profile(
    segment_status_df: pd.DataFrame,
    segments_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build per-segment velocity statistics profile."""
    log_step("Building segment velocity profile...")
    if "segment_id" not in segment_status_df.columns or "velocity" not in segment_status_df.columns:
        log_info("  segment_status missing required columns, skipping profile")
        return pd.DataFrame()

    stats = segment_status_df.groupby("segment_id")["velocity"].agg([
        "mean", "std", "median", "min", "max",
        lambda x: x.quantile(0.25),
        lambda x: x.quantile(0.75),
        "count",
    ]).reset_index()
    stats.columns = [
        "segment_id", "seg_vel_mean", "seg_vel_std", "seg_vel_median",
        "seg_vel_min", "seg_vel_max", "seg_vel_q25", "seg_vel_q75", "seg_vel_count",
    ]
    stats["seg_vel_iqr"] = stats["seg_vel_q75"] - stats["seg_vel_q25"]
    stats["seg_vel_cv"] = (stats["seg_vel_std"] / stats["seg_vel_mean"].replace(0, 1)).clip(0, 10)

    profile = segments_df.rename(columns={"_id": "segment_id"}).merge(stats, on="segment_id", how="left")
    log_info(f"  Segment profile: {len(profile)} segments with velocity stats")
    return profile


def build_period_profile(train_df: pd.DataFrame) -> pd.DataFrame:
    """Build period statistics profile.

    P0-2 FIX: period_LOS_*_ratio and period_los_mode are TARGET LEAKAGE —
    they encode exact LOS class proportions per period. Returns empty DataFrame.
    """
    log_step("Building period LOS profile...")
    # Target leakage: period_LOS_*_ratio and period_los_mode are removed.
    # They encode exact class proportions per period which leaks the target.
    return pd.DataFrame()


def build_segment_period_profile(train_df: pd.DataFrame) -> pd.DataFrame:
    """Build segment-period profile.

    P0-2 FIX: seg_period_los_mode and seg_period_los_entropy are TARGET LEAKAGE —
    they encode LOS class info per (segment, period). Returns only seg_period_count.
    """
    log_step("Building segment-period LOS profile...")
    if "segment_id" not in train_df.columns or "period" not in train_df.columns:
        return pd.DataFrame()

    # P0-2 FIX: seg_period_los_mode and seg_period_los_entropy are TARGET LEAKAGE.
    # We keep only the count (how many observations per segment-period), which is safe.
    counts = (
        train_df.groupby(["segment_id", "period"])
        .size()
        .reset_index(name="seg_period_count")
    )
    log_info(f"  Segment-period profile: {len(counts)} combinations (count only, no LOS leakage)")
    return counts


def build_dayofweek_profile(train_df: pd.DataFrame) -> pd.DataFrame:
    """Build weekday count profile.

    P0-2 FIX: seg_weekday_los_mode is TARGET LEAKAGE — encodes LOS per (segment, weekday).
    Returns only the count per (segment, weekday).
    """
    log_step("Building weekday LOS profile...")
    if "segment_id" not in train_df.columns or "weekday" not in train_df.columns:
        return pd.DataFrame()

    dow = (
        train_df.groupby(["segment_id", "weekday"])
        .size()
        .reset_index(name="seg_weekday_count")
    )
    log_info(f"  Weekday profile: {len(dow)} (segment, weekday) combinations (count only, no LOS leakage)")
    return dow


# =============================================================================
# 8. NEIGHBOR SEGMENT FEATURES
# =============================================================================

def compute_neighbor_features(
    df: pd.DataFrame,
    segments_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Tính đặc trưng V/C ratio của các đoạn đường liền kề (chia sẻ node đầu/cuối).

    Lý do: Tắc nghẽn ở đoạn đường lân cận ảnh hưởng trực tiếp đến LOS của đoạn hiện tại
    (ví dụ: xe không thể thoát khỏi đoạn đường bị tắc từ đoạn liền kề).

    Features được thêm:
      - neighbor_avg_vc: V/C ratio trung bình của các đoạn liền kề
      - neighbor_max_vc: V/C ratio tối đa của các đoạn liền kề
      - neighbor_min_vc: V/C ratio tối thiểu của các đoạn liền kề
      - neighbor_count: Số lượng đoạn đường liền kề
    """
    df = df.copy()
    log_step("Computing neighbor segment features...")

    if "vc_ratio" not in df.columns or "segment_id" not in df.columns:
        log_info("  Thiếu vc_ratio hoặc segment_id, bỏ qua neighbor features")
        return df

    if segments_df is None or segments_df.empty:
        log_info("  segments_df trống, bỏ qua neighbor features")
        return df

    # Xây dựng bảng ánh xạ: segment_id → (s_node_id, e_node_id)
    segs = segments_df.rename(columns={"_id": "segment_id"})[["segment_id", "s_node_id", "e_node_id"]].copy()
    segs["s_node_id"] = segs["s_node_id"].astype(str)
    segs["e_node_id"] = segs["e_node_id"].astype(str)

    # Lấy V/C ratio hiện có trong df (dùng trung bình nếu có nhiều bản ghi cùng segment)
    vc_map = df.groupby("segment_id")["vc_ratio"].mean().reset_index()
    vc_map.columns = ["segment_id", "vc_ratio_seg"]

    # Merge node info vào vc_map
    vc_map = vc_map.merge(segs, on="segment_id", how="left")

    # Tạo bảng lookup: node → list of vc_ratio của các segment kết nối
    node_vc_records = []
    for _, row in vc_map.iterrows():
        node_vc_records.append({"node": row["s_node_id"], "vc": row["vc_ratio_seg"]})
        node_vc_records.append({"node": row["e_node_id"], "vc": row["vc_ratio_seg"]})
    node_vc_df = pd.DataFrame(node_vc_records).dropna()
    node_vc_agg = node_vc_df.groupby("node")["vc"].agg(["mean", "max", "min", "count"]).reset_index()
    node_vc_agg.columns = ["node", "node_vc_mean", "node_vc_max", "node_vc_min", "node_vc_count"]

    # Merge theo s_node_id và e_node_id, lấy trung bình cả 2 đầu
    df["s_node_id_str"] = df.get("s_node_id", pd.Series(dtype=str)).astype(str)
    df["e_node_id_str"] = df.get("e_node_id", pd.Series(dtype=str)).astype(str)

    df = df.merge(node_vc_agg.rename(columns={
        "node": "s_node_id_str", "node_vc_mean": "s_vc_mean",
        "node_vc_max": "s_vc_max", "node_vc_min": "s_vc_min", "node_vc_count": "s_vc_count"
    }), on="s_node_id_str", how="left")

    df = df.merge(node_vc_agg.rename(columns={
        "node": "e_node_id_str", "node_vc_mean": "e_vc_mean",
        "node_vc_max": "e_vc_max", "node_vc_min": "e_vc_min", "node_vc_count": "e_vc_count"
    }), on="e_node_id_str", how="left")

    # Tổng hợp từ 2 đầu node
    df["neighbor_avg_vc"] = df[["s_vc_mean", "e_vc_mean"]].mean(axis=1)
    df["neighbor_max_vc"] = df[["s_vc_max", "e_vc_max"]].max(axis=1)
    df["neighbor_min_vc"] = df[["s_vc_min", "e_vc_min"]].min(axis=1)
    df["neighbor_count"] = df[["s_vc_count", "e_vc_count"]].sum(axis=1)

    # Drop các cột tạm
    drop_cols = ["s_node_id_str", "e_node_id_str",
                 "s_vc_mean", "s_vc_max", "s_vc_min", "s_vc_count",
                 "e_vc_mean", "e_vc_max", "e_vc_min", "e_vc_count"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    log_info("  Added: neighbor_avg_vc, neighbor_max_vc, neighbor_min_vc, neighbor_count")
    return df


# =============================================================================
# 9. MAIN PIPELINE
# =============================================================================

def engineer_features(
    train_df: pd.DataFrame,
    segment_status_df: pd.DataFrame,
    segments_df: pd.DataFrame,
    nodes_df: pd.DataFrame,
    mode: Literal["train", "inference"] = "train",
) -> tuple[pd.DataFrame, dict]:
    """
    Full feature engineering pipeline.

    Args:
        train_df: Preprocessed training data (from preprocessing.py)
        segment_status_df: Historical segment velocity records
        segments_df: Segment metadata
        nodes_df: Node coordinates
        mode: 'train' includes lag/rolling; 'inference' skips temporal features

    Returns:
        DataFrame with all engineered features + feature info dict
    """
    log(f"\n{'=' * 60}")
    log(f"  Feature Engineering Pipeline")
    log(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'=' * 60}")
    log(f"  Input shape: {train_df.shape}")

    df = train_df.copy()
    feat_info = {}

    # ---- 1. Temporal ----
    log(f"\n[1/8] Temporal features...")
    df = extract_temporal_features(df, period_col="period", date_col="date")

    # ---- 2. Spatial / Geometry ----
    log(f"\n[2/8] Spatial features...")
    df = compute_geometry_features(df)
    # Bug #1 fix: kiểm tra nodes_df thực sự được truyền vào (trước đây dùng `"nodes" in dir()` luôn False)
    if "midpoint_long" in df.columns and nodes_df is not None and not nodes_df.empty:
        df = compute_spatial_features_balltree(df, nodes_df, k=5, density_radius_km=0.5)
    else:
        log_info("  BallTree skipped: nodes_df không hợp lệ hoặc thiếu midpoint_long")

    # Bug #1 FIX: compute_network_features được định nghĩa nhưng chưa bao giờ được gọi đúng cách.
    # Merge trực tiếp node features vào df theo s_node_id / e_node_id,
    # không qua seg_net (seg_net chứa stats theo node_id, không phải segment context).
    if segments_df is not None and not segments_df.empty and nodes_df is not None and not nodes_df.empty:
        node_net_df, _ = compute_network_features(segments_df, nodes_df)
        # Chuan hoa node_degree cua s_node
        s_node_deg = node_net_df[["_id", "node_degree", "start_degree", "is_dead_end", "is_intersection", "is_4way"]].copy()
        s_node_deg = s_node_deg.rename(columns={
            "_id": "s_node_id",
            "node_degree": "node_degree",
            "start_degree": "start_degree",
            "is_dead_end": "is_dead_end",
            "is_intersection": "is_intersection",
            "is_4way": "is_4way",
        })
        if "s_node_id" in df.columns:
            df = df.merge(s_node_deg, on="s_node_id", how="left")
        # Chuan hoa node_degree cua e_node
        e_node_deg = node_net_df[["_id", "end_degree"]].copy()
        e_node_deg = e_node_deg.rename(columns={"_id": "e_node_id", "end_degree": "end_degree"})
        if "e_node_id" in df.columns:
            df = df.merge(e_node_deg, on="e_node_id", how="left")
        # Drop seg_net columns (node-level aggregates, not segment context)
        for col in ["seg_avg_degree", "seg_max_degree", "seg_dead_ends", "seg_intersections"]:
            if col in df.columns:
                df = df.drop(columns=[col])
        log_info("  Merged network features: node_degree, start_degree, end_degree, is_dead_end, is_intersection, is_4way")
    else:
        log_info("  Network features skipped: segments_df hoặc nodes_df không hợp lệ")

    # ---- 3. Infrastructure ----
    log(f"\n[3/8] Infrastructure features...")
    df = compute_infrastructure_features(df)

    # ---- 4. Traffic-derived ----
    log(f"\n[4/8] Traffic-derived features...")
    df = compute_traffic_features(df)
    # Bug #4 fix: z-score của vc_ratio có ý nghĩa hơn hist_vel_mean (là giá trị tổng hợp)
    if "vc_ratio" in df.columns:
        df = compute_velocity_zscore(df, group_col="segment_id", val_col="vc_ratio")
    elif "hist_vel_mean" in df.columns:
        df = compute_velocity_zscore(df, group_col="segment_id", val_col="hist_vel_mean")

    # ---- 5. Lag / Rolling / Diff (train mode only) ----
    if mode == "train":
        log(f"\n[5/8] Lag and rolling features (train mode)...")

        # Build profiles from segment_status
        seg_profile = build_segment_profile(segment_status_df, segments_df)
        if not seg_profile.empty:
            merge_cols = ["segment_id", "seg_vel_mean", "seg_vel_std", "seg_vel_median",
                          "seg_vel_min", "seg_vel_max", "seg_vel_q25", "seg_vel_q75",
                          "seg_vel_iqr", "seg_vel_cv", "seg_vel_count"]
            cols_present = [c for c in merge_cols if c in seg_profile.columns]
            df = df.merge(seg_profile[cols_present], on="segment_id", how="left")
            log_info(f"  Merged segment profile: {len(cols_present)-1} cols")

        # Period profile
        # P0-2 FIX: period_LOS_*_ratio and period_los_mode are TARGET LEAKAGE.
        # build_period_profile now returns empty DataFrame. Period features are skipped.
        period_profile = build_period_profile(train_df)
        if not period_profile.empty:
            df = df.merge(period_profile, on="period", how="left")
            log_info(f"  Merged period profile: {len(period_profile.columns)-1} cols")

        # Segment-period profile
        seg_period_profile = build_segment_period_profile(train_df)
        if not seg_period_profile.empty:
            # Only seg_period_count is safe (no LOS leakage)
            merge_cols = ["segment_id", "period", "seg_period_count"]
            cols_present = [c for c in merge_cols if c in seg_period_profile.columns]
            df = df.merge(seg_period_profile[cols_present], on=["segment_id", "period"], how="left")
            log_info(f"  Merged seg-period profile: {len(cols_present)-1} cols")

        # Weekday profile
        dow_profile = build_dayofweek_profile(train_df)
        if not dow_profile.empty:
            merge_cols = ["segment_id", "weekday", "seg_weekday_count"]
            cols_present = [c for c in merge_cols if c in dow_profile.columns]
            df = df.merge(dow_profile[cols_present], on=["segment_id", "weekday"], how="left")
            log_info(f"  Merged weekday profile: {len(cols_present)-1} cols")

        # Lag / rolling on segment_status time series
        if not segment_status_df.empty and "segment_id" in segment_status_df.columns:
            seg_ts = segment_status_df.copy()
            if "updated_at" in seg_ts.columns:
                seg_ts["updated_at"] = pd.to_datetime(seg_ts["updated_at"], errors="coerce")
                seg_ts = seg_ts.sort_values(["segment_id", "updated_at"])
                seg_ts = compute_lag_features(seg_ts, group_col="segment_id",
                                               sort_col="updated_at", val_col="velocity")
                seg_ts = compute_rolling_features(seg_ts, group_col="segment_id",
                                                   sort_col="updated_at", val_col="velocity")
                seg_ts = compute_diff_features(seg_ts, group_col="segment_id",
                                                sort_col="updated_at", val_col="velocity")

                # Bug #3 fix: không dùng .last() mà join theo (segment_id, date + period)
                # Để mỗi bản ghi trong train_df nhận được lag của đú ng thời gian tương ứng
                lag_cols_needed = [c for c in seg_ts.columns if (
                    c.startswith("velocity_lag_") or c.startswith("velocity_roll_") or
                    c.startswith("velocity_diff_") or c.startswith("velocity_pct_")
                )]

                # Chọn bản ghi gần nhất trong segment_status so với từng (segment_id, date, period)
                # Bằng cách floor timestamp xuống mức 30 phút (hoặc chu kỳ phù hợp)
                seg_ts["ts_floor"] = pd.to_datetime(seg_ts["updated_at"], utc=True).dt.tz_localize(None).dt.floor("30min")

                # Tạo key tương ứng trong df
                if "date" in df.columns and "period_hour" in df.columns:
                    df["_ts_approx"] = pd.to_datetime(df["date"], errors="coerce") + \
                        pd.to_timedelta(df["period_hour"].fillna(0).astype(int), unit="h") + \
                        pd.to_timedelta(df["period_minute"].fillna(0).astype(int), unit="m")
                    df["_ts_floor"] = pd.to_datetime(df["_ts_approx"], utc=True).dt.tz_localize(None).dt.floor("30min")

                    # Tìm bản ghi mới nhất trong seg_ts không vượt quá _ts_floor (no future leakage)
                    seg_ts_lag = seg_ts[["segment_id", "ts_floor"] + lag_cols_needed].dropna(subset=["ts_floor"])

                    # Sắp xếp để merge_asof hoạt động (phải sort theo timestamp)
                    seg_ts_lag = seg_ts_lag.sort_values("ts_floor")
                    df_sorted = df.sort_values("_ts_floor")

                    merged = pd.merge_asof(
                        df_sorted,
                        seg_ts_lag.rename(columns={"ts_floor": "_ts_floor"}),
                        on="_ts_floor",
                        by="segment_id",
                        direction="backward",
                        suffixes=("", "_lag_status"),
                    )

                    # Khôi phục thứ tự và drop cột tạm
                    df = merged.sort_index().drop(columns=["_ts_approx", "_ts_floor"], errors="ignore")
                    log_info(f"  Merged {len(lag_cols_needed)} lag/rolling features qua merge_asof (chính xác theo thời gian)")
                else:
                    # Fallback: lấy summary thống kê trên toàn bộ lịch sử của segment
                    log_info("  [WARNING] Không có date/period_hour — fallback láy summary lag ợ cấp độ segment")
                    lag_agg = (
                        seg_ts.groupby("segment_id")[lag_cols_needed]
                        .agg("mean")  # dùng mean thay vì .last() để an toàn hơn
                        .reset_index()
                    )
                    df = df.merge(lag_agg, on="segment_id", how="left")
                    log_info("  Merged lag summary (mean aggregation) vì không có timestamp chính xác")

    # ---- 6. Interaction features ----
    log(f"\n[6/8] Interaction features...")
    df = create_interaction_features(df)

    # ---- 6b. Neighbor segment V/C features (Nhóm 3 mới) ----
    log(f"\n[6b/8] Neighbor segment features...")
    df = compute_neighbor_features(df, segments_df)

    # ---- 7. Encode remaining categoricals ----
    log(f"\n[7/8] Encoding remaining categoricals...")
    encodings = {}
    # P0-2 FIX: seg_period_los_mode, seg_weekday_los_mode, period_los_mode are
    # TARGET LEAKAGE and have been removed from the data. They are kept in the list
    # below for safety (the `if col in df.columns` guard will skip them).
    cat_cols = ["time_of_day_cat", "season", "congestion_level", "speed_limit_category",
                "seg_period_los_mode", "seg_weekday_los_mode", "period_los_mode"]
    for col in cat_cols:
        if col in df.columns:
            vals = sorted(df[col].dropna().unique().tolist())
            mapping = {v: i for i, v in enumerate(vals)}
            encodings[col] = mapping
            df[f"{col}_enc"] = df[col].map(mapping).fillna(-1).astype(int)
            log_info(f"  Encoded: {col} -> {col}_enc  ({len(mapping)} categories)")

    # ---- 8. Final cleanup ----
    log(f"\n[8/8] Final cleanup...")
    # Drop fully null columns
    null_cols = df.columns[df.isna().all()].tolist()
    if null_cols:
        df = df.drop(columns=null_cols)
        log_info(f"  Dropped all-null columns: {null_cols}")

    log(f"\n{'=' * 60}")
    log(f"  Feature engineering complete!")
    log(f"  Final shape: {df.shape[0]:,} rows x {df.shape[1]} cols")
    log(f"{'=' * 60}")

    # Feature list
    # Bug #8 fix: congestion_level_enc là near-leakage (dẫn xuất trực tiếp từ vc_ratio ở cùng ngưỡng LOS)
    # nên tách khỏi feature_names, giữ lại như một diagnostic column
    # P0-2 FIX: These columns encode target (LOS) information and are target leakage.
    # period_LOS_*_ratio: exact class proportions per period (removed from build)
    # seg_period_los_mode, seg_weekday_los_mode, period_los_mode: LOS mode per group (removed)
    # seg_period_los_entropy: entropy of LOS distribution per group (removed)
    # congestion_level_enc: derived from vc_ratio at same thresholds as LOS (near-leakage)
    target_cols = {
        "LOS", "LOS_numeric", "LOS_enc", "date", "updated_at",
        "segment_id", "s_node_id", "e_node_id", "street_id", "period",
        "street_name", "street_type", "street_full_name", "street_catalog_type",
        "time_of_day", "time_of_day_cat", "season", "congestion_level", "speed_limit_category",
        "_id",  # Internal ID, not a feature
        "seg_street_type",  # Non-numeric string column from merge
        # Target leakage columns
        "period_LOS_A_ratio", "period_LOS_B_ratio", "period_LOS_C_ratio",
        "period_LOS_D_ratio", "period_LOS_E_ratio", "period_LOS_F_ratio",
        "seg_period_los_mode", "seg_period_los_entropy",
        "seg_weekday_los_mode",
        "period_los_mode",
        "congestion_level_enc",
    }
    feature_cols = [c for c in df.columns if c not in target_cols]

    feat_info = {
        "total_cols": len(df.columns),
        "num_features": len(feature_cols),
        "feature_names": feature_cols,
        "categorical_cols": list(encodings.keys()),
    }
    return df, feat_info


def feature_engineering_pipeline():
    """Load preprocessed data and run full feature engineering."""
    import json

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log(f"\nLoading preprocessed data from {OUTPUT_DIR}...")
    master = pd.read_csv(OUTPUT_DIR / "train_features_base.csv")
    nodes = pd.read_csv(OUTPUT_DIR / "nodes_clean.csv")
    segments = pd.read_csv(OUTPUT_DIR / "segments_clean.csv")
    segment_status = pd.read_csv(OUTPUT_DIR / "segment_status_clean.csv")

    log(f"  train_features_base.csv: {master.shape}")
    log(f"  nodes_clean.csv: {nodes.shape}")
    log(f"  segments_clean.csv: {segments.shape}")
    log(f"  segment_status_clean.csv: {segment_status.shape}")

    log("\nStarting feature engineering...")
    df_features, feat_info = engineer_features(
        train_df=master,
        segment_status_df=segment_status,
        segments_df=segments,
        nodes_df=nodes,
        mode="train",
    )

    log("\nSaving outputs...")
    # CSV
    csv_path = OUTPUT_DIR / "train_features.csv"
    df_features.to_csv(csv_path, index=False, encoding="utf-8-sig")
    csv_size = csv_path.stat().st_size / 1_048_576
    log(f"  Saved: {csv_path.name} ({csv_size:.1f} MB)")

    # Feature info
    with open(OUTPUT_DIR / "feature_info.json", "w", encoding="utf-8") as f:
        json.dump(feat_info, f, ensure_ascii=False, indent=2)
    log(f"  Saved: feature_info.json ({feat_info['num_features']} features)")

    log(f"\n  Top 30 feature columns:")
    for i, col in enumerate(feat_info["feature_names"][:30], 1):
        log(f"    {i:2d}. {col}")

    log(f"\n{'=' * 60}")
    log(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'=' * 60}\n")

    return df_features, feat_info


if __name__ == "__main__":
    feature_engineering_pipeline()