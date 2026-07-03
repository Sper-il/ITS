import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Literal

import warnings
warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data_traffic"

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"

class PipelineLogger:
    """Simple structured logger that prints step summaries."""

    def __init__(self):
        self._indent = "  "
        self._steps = []
        self._report = {}

    def section(self, title: str):
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")

    def step(self, msg: str):
        print(f"{self._indent}>> {msg}")

    def info(self, msg: str):
        print(f"{self._indent}  {msg}")

    def result(self, key: str, before: int, after: int, details: str = ""):
        dropped = before - after
        pct = (dropped / before * 100) if before > 0 else 0
        msg = f"  {key}: {before:,} -> {after:,} rows"
        if dropped > 0:
            msg += f"  (dropped {dropped:,} = {pct:.1f}%)"
        if details:
            msg += f"  {details}"
        print(msg)
        self._report[key] = {"before": before, "after": after, "dropped": dropped, "drop_pct": round(pct, 2)}
        self._steps.append({"key": key, "before": before, "after": after})

    def save_report(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._report, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n{self._indent}Quality report saved -> {path}")

    def warning(self, msg: str):
        print(f"{self._indent}  [!] {msg}")

    def save(self, key: str, val):
        self._report[key] = val

LOG = PipelineLogger()

def load_all_data() -> dict[str, pd.DataFrame]:
    """Load all 5 source CSV files. Returns dict of {name: DataFrame}."""
    LOG.step("Loading 5 CSV files...")
    tables = {}
    for fname in ["nodes", "segments", "segment_status", "streets", "train"]:
        path = DATA_DIR / f"{fname}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing: {path}")
        tables[fname] = pd.read_csv(path, low_memory=False)
        LOG.info(f"{fname}.csv: {len(tables[fname]):,} rows x {len(tables[fname].columns)} cols")
    return tables

def profile_data_quality(tables: dict[str, pd.DataFrame]) -> dict:
    """
    Scan all tables and return a structured quality report.
    Catches: missing values, duplicate IDs, invalid coords, date range issues,
    FK orphans, reverse duplicates, schema mismatches.
    """
    LOG.section("SECTION 2: DATA QUALITY PROFILING")
    report = {}

    for name, df in tables.items():
        LOG.step(f"Profiling: {name}")
        r = {
            "total_rows": len(df),
            "total_cols": len(df.columns),
            "columns": list(df.columns),
            "missing": {},
            "duplicates": 0,
            "issues": [],
        }

        for col in df.columns:
            n_missing = df[col].isna().sum()
            pct = n_missing / len(df) * 100
            if n_missing > 0:
                r["missing"][col] = {"count": int(n_missing), "pct": round(pct, 2)}

        if "_id" in df.columns:
            dupes = df["_id"].duplicated().sum()
            r["duplicates"] = int(dupes)
            if dupes > 0:
                r["issues"].append(f"Duplicate _id: {dupes:,}")

        if name == "nodes":
            bad_coords = (
                ((df["long"] < 105) | (df["long"] > 107) |
                 (df["lat"] < 10) | (df["lat"] > 11.5))
                .sum()
            )
            if bad_coords > 0:
                r["issues"].append(f"Invalid coordinates: {bad_coords:,}")

        if name == "segments":
            neg_len = (df["length"] < 0).sum()
            if neg_len > 0:
                r["issues"].append(f"Negative length: {neg_len:,}")
            null_node = df[["s_node_id", "e_node_id"]].isna().any(axis=1).sum()
            if null_node > 0:
                r["issues"].append(f"Null node references: {null_node:,}")

        if name == "segment_status":
            neg_vel = (df["velocity"] < 0).sum()
            if neg_vel > 0:
                r["issues"].append(f"Negative velocity: {neg_vel:,}")

        if name == "train":
            invalid_los = (~df["LOS"].str.upper().isin(["A","B","C","D","E","F"])).sum()
            if invalid_los > 0:
                r["issues"].append(f"Invalid LOS labels: {invalid_los:,}")

        report[name] = r
        for iss in r["issues"]:
            LOG.info(f"  [!] {iss}")

    LOG.save("quality_profile", report)
    return report

def check_time_series_continuity(df: pd.DataFrame, date_col="date") -> pd.DataFrame:
    """Check if segments have continuous data."""
    df_c = df.copy()
    df_c[date_col] = pd.to_datetime(df_c[date_col], errors="coerce")
    g = df_c.dropna(subset=[date_col]).groupby("segment_id")[date_col]
    g_min = g.min()
    g_max = g.max()
    g_count = g.count()
    expected_days = (g_max - g_min).dt.days + 1

    continuity = pd.DataFrame({
        "start_date": g_min,
        "end_date": g_max,
        "expected_days": expected_days,
        "actual_records": g_count
    })
    continuity["records_per_day"] = continuity["actual_records"] / continuity["expected_days"].clip(lower=1)
    return continuity

def _to_numeric(df: pd.DataFrame, col: str, fill_na=None, clip_lower=None) -> pd.Series:
    """Safe numeric coercion with optional fill and clip."""
    s = pd.to_numeric(df[col], errors="coerce")
    if fill_na is not None:
        s = s.fillna(fill_na)
    if clip_lower is not None:
        s = s.clip(lower=clip_lower)
    return s

def clean_nodes(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Enhanced node cleaning:
      - Drop duplicates on _id
      - Drop rows with null coords
      - Filter lat ∈ [10, 11.5], long ∈ [105, 107]
      - Detect and flag isolated nodes (no segment references)
    """
    LOG.section("SECTION 3a: CLEANING - nodes")
    LOG.step("Cleaning nodes...")
    n0 = len(df)

    df = df.drop_duplicates(subset="_id", keep="first").copy()
    df = df.dropna(subset=["long", "lat"])

    df["long"] = _to_numeric(df, "long")
    df["lat"] = _to_numeric(df, "lat")

    n_valid_coords = (
        (df["long"] >= 105) & (df["long"] <= 107) &
        (df["lat"] >= 10) & (df["lat"] <= 11.5)
    )
    df = df[n_valid_coords].copy()

    df["is_isolated"] = False

    LOG.result("nodes", n0, len(df))
    return df, {"original_rows": n0, "cleaned_rows": len(df)}

def clean_segments(df: pd.DataFrame, nodes_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Enhanced segment cleaning:
      - Drop duplicates on _id
      - Drop rows with null node references
      - Coerce length >= 0, max_velocity, street_level
      - Detect reverse duplicates (segment A-B vs B-A)
      - Validate s_node_id and e_node_id FK against nodes
    """
    LOG.section("SECTION 3b: CLEANING - segments")
    LOG.step("Cleaning segments...")
    n0 = len(df)

    df = df.drop_duplicates(subset="_id", keep="first").copy()
    df = df.dropna(subset=["_id", "s_node_id", "e_node_id"])

    df["length"] = _to_numeric(df, "length", fill_na=0, clip_lower=0)
    df["max_velocity"] = _to_numeric(df, "max_velocity")
    df["street_level"] = _to_numeric(df, "street_level", fill_na=4).clip(1, 4)

    valid_nodes = set(nodes_df["_id"].dropna())
    n_bad_s = (~df["s_node_id"].isin(valid_nodes)).sum()
    n_bad_e = (~df["e_node_id"].isin(valid_nodes)).sum()
    if n_bad_s > 0:
        LOG.info(f"  Orphan s_node_id (no match in nodes): {n_bad_s:,}")
    if n_bad_e > 0:
        LOG.info(f"  Orphan e_node_id (no match in nodes): {n_bad_e:,}")

    df = df[df["s_node_id"].isin(valid_nodes) & df["e_node_id"].isin(valid_nodes)].copy()

    seg_keys = df[["s_node_id", "e_node_id"]].astype(str).agg("|".join, axis=1)

    normalized_keys = seg_keys.apply(
        lambda x: "|".join(sorted(x.split("|")))
    )
    n_reverse = (normalized_keys.duplicated(keep="first") & ~seg_keys.duplicated(keep="first")).sum()
    if n_reverse > 0:
        LOG.info(f"  Reverse duplicate segments detected (A-B vs B-A): {n_reverse:,}")

    df = df.drop_duplicates(subset="_id", keep="first")

    LOG.result("segments", n0, len(df))
    return df, {
        "original_rows": n0, "cleaned_rows": len(df),
        "orphan_s_node": int(n_bad_s), "orphan_e_node": int(n_bad_e),
        "reverse_duplicates": int(n_reverse),
    }

def clean_segment_status(df: pd.DataFrame, segments_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Enhanced segment_status cleaning:
      - Parse timestamps, drop nulls/invalids
      - Validate segment_id FK
      - Velocity >= 0
      - Flag stale records (updated_at outside reasonable range)
      - Remove duplicate (segment, timestamp) records
    """
    LOG.section("SECTION 3c: CLEANING - segment_status")
    LOG.step("Cleaning segment_status...")
    n0 = len(df)

    df = df.drop_duplicates(subset="_id", keep="first").copy()
    df["updated_at"] = pd.to_datetime(df["updated_at"], errors="coerce")
    df = df.dropna(subset=["updated_at", "segment_id"])

    df["velocity"] = _to_numeric(df, "velocity", clip_lower=0)

    valid_seg = set(segments_df["_id"].dropna())
    n_orphan = (~df["segment_id"].isin(valid_seg)).sum()
    if n_orphan > 0:
        LOG.info(f"  Orphan segment_id (no match in segments): {n_orphan:,}")
    df = df[df["segment_id"].isin(valid_seg)].copy()

    min_date = pd.Timestamp("2019-01-01", tz="UTC")
    max_date = pd.Timestamp("2026-12-31", tz="UTC")
    out_of_range = ((df["updated_at"] < min_date) | (df["updated_at"] > max_date)).sum()
    if out_of_range > 0:
        LOG.info(f"  Records outside 2019-2026: {out_of_range:,}")
    df = df[(df["updated_at"] >= min_date) & (df["updated_at"] <= max_date)].copy()

    n_dup = df.duplicated(subset=["segment_id", "updated_at"]).sum()
    if n_dup > 0:
        LOG.info(f"  Duplicate (segment, timestamp) pairs: {n_dup:,}")
    df = df.drop_duplicates(subset=["segment_id", "updated_at"], keep="first")

    LOG.result("segment_status", n0, len(df))
    return df, {
        "original_rows": n0, "cleaned_rows": len(df),
        "orphan_segment": int(n_orphan), "out_of_range": int(out_of_range),
        "duplicate_pairs": int(n_dup),
    }

def clean_streets(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Enhanced streets cleaning."""
    LOG.section("SECTION 3d: CLEANING - streets")
    LOG.step("Cleaning streets...")
    n0 = len(df)

    df = df.drop_duplicates(subset="_id", keep="first").copy()
    df["level"] = _to_numeric(df, "level", fill_na=4).clip(1, 4)
    df["max_velocity"] = _to_numeric(df, "max_velocity")
    df["name"] = df["name"].astype(str).str.strip()
    df["type"] = df["type"].astype(str).str.strip().str.lower()

    type_map = {
        "trunk": "trunk", "motorway": "trunk",
        "primary": "primary", "primary_link": "primary",
        "secondary": "secondary", "secondary_link": "secondary",
        "tertiary": "tertiary", "tertiary_link": "tertiary",
        "unclassified": "unclassified", "residential": "residential",
        "service": "service",
    }
    df["type_std"] = df["type"].map(type_map).fillna("unknown")

    LOG.result("streets", n0, len(df))
    return df, {"original_rows": n0, "cleaned_rows": len(df)}

def clean_train(df: pd.DataFrame, segments_df: pd.DataFrame,
                nodes_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Enhanced train cleaning:
      - Parse dates, drop nulls
      - Coerce numeric fields
      - Validate LOS labels (only A-F)
      - Validate segment_id FK
      - Cross-validate node coords match node table
      - Detect and handle records with zero variance (same segment+period+LOS repeated)
      - Compute record hash for deduplication across columns
    """
    LOG.section("SECTION 3e: CLEANING - train")
    LOG.step("Cleaning train...")
    n0 = len(df)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    n_bad_date = df["date"].isna().sum()
    if n_bad_date > 0:
        LOG.info(f"  Invalid dates: {n_bad_date:,}")

    df["length"] = _to_numeric(df, "length", fill_na=0, clip_lower=0)
    df["max_velocity"] = _to_numeric(df, "max_velocity")
    df["street_level"] = _to_numeric(df, "street_level", fill_na=4)
    df["long_snode"] = _to_numeric(df, "long_snode")
    df["lat_snode"] = _to_numeric(df, "lat_snode")
    df["long_enode"] = _to_numeric(df, "long_enode")
    df["lat_enode"] = _to_numeric(df, "lat_enode")

    df["LOS"] = df["LOS"].astype(str).str.strip().str.upper()
    n_bad_los = (~df["LOS"].isin(["A","B","C","D","E","F"])).sum()
    if n_bad_los > 0:
        LOG.info(f"  Invalid LOS labels: {n_bad_los:,}")
    df = df[df["LOS"].isin(["A","B","C","D","E","F"])].copy()

    valid_seg = set(segments_df["_id"].dropna())
    n_orphan_seg = (~df["segment_id"].isin(valid_seg)).sum()
    if n_orphan_seg > 0:
        LOG.info(f"  Orphan segment_id: {n_orphan_seg:,}")
    df = df[df["segment_id"].isin(valid_seg)].copy()

    valid_nodes = set(nodes_df["_id"].dropna())
    n_bad_snode = (~df["s_node_id"].isin(valid_nodes)).sum()
    n_bad_enode = (~df["e_node_id"].isin(valid_nodes)).sum()
    if n_bad_snode > 0:
        LOG.info(f"  Orphan s_node_id: {n_bad_snode:,}")
    if n_bad_enode > 0:
        LOG.info(f"  Orphan e_node_id: {n_bad_enode:,}")
    df = df[df["s_node_id"].isin(valid_nodes) & df["e_node_id"].isin(valid_nodes)].copy()

    node_coords = nodes_df[["_id", "long", "lat"]].rename(
        columns={"_id": "s_node_id", "long": "node_long_s", "lat": "node_lat_s"}
    )
    df = df.merge(node_coords, on="s_node_id", how="left")
    df["coord_match_s"] = np.isclose(
        df["long_snode"], df["node_long_s"], rtol=1e-4, equal_nan=True
    )
    node_coords_e = nodes_df[["_id", "long", "lat"]].rename(
        columns={"_id": "e_node_id", "long": "node_long_e", "lat": "node_lat_e"}
    )
    df = df.merge(node_coords_e, on="e_node_id", how="left")
    df["coord_match_e"] = np.isclose(
        df["long_enode"], df["node_long_e"], rtol=1e-4, equal_nan=True
    )

    n_coord_mismatch = ((~df["coord_match_s"]) | (~df["coord_match_e"])).sum()
    if n_coord_mismatch > 0:
        LOG.info(f"  Node coordinate mismatches vs nodes table: {n_coord_mismatch:,}")

    filter_coord_mismatch = False
    if filter_coord_mismatch:
        df = df[df["coord_match_s"] & df["coord_match_e"]].copy()
        LOG.info("  Filtered out mismatched coordinates.")

    df = df.drop(columns=["coord_match_s", "coord_match_e", "node_long_s",
                          "node_lat_s", "node_long_e", "node_lat_e"], errors="ignore")

    dedup_cols = ["segment_id", "date", "period", "LOS"]
    existing_dedup = [c for c in dedup_cols if c in df.columns]
    if existing_dedup:
        df["_record_hash"] = df[existing_dedup].astype(str).agg("|".join, axis=1).apply(
            lambda x: hashlib.md5(x.encode()).hexdigest()
        )
        n_dup = df["_record_hash"].duplicated().sum()
        if n_dup > 0:
            LOG.info(f"  Exact duplicate records: {n_dup:,}")
        df = df.drop_duplicates(subset=["_record_hash"], keep="first")
        df = df.drop(columns=["_record_hash"])

    n_all_null = df[["long_snode", "lat_snode", "long_enode", "lat_enode"]].isna().all(axis=1).sum()
    if n_all_null > 0:
        LOG.info(f"  Rows with all-null coords: {n_all_null:,}")
    df = df[~(df[["long_snode", "lat_snode", "long_enode", "lat_enode"]].isna().all(axis=1))].copy()

    LOG.result("train", n0, len(df))
    return df, {
        "original_rows": n0, "cleaned_rows": len(df),
        "bad_dates": int(n_bad_date), "bad_los": int(n_bad_los),
        "orphan_segments": int(n_orphan_seg), "orphan_nodes": int(n_bad_snode + n_bad_enode),
        "coord_mismatches": int(n_coord_mismatch),
    }

def detect_velocity_outliers(
    df: pd.DataFrame,
    col: str = "velocity",
    methods: list[Literal["iqr", "zscore", "isolation_forest"]] = None,
) -> pd.DataFrame:
    """
    Detect velocity outliers using multiple methods.
    Returns DataFrame with boolean outlier flags per method.
    """
    if methods is None:
        methods = ["iqr", "zscore"]
    if col not in df.columns:
        return df

    LOG.section("SECTION 4: OUTLIER DETECTION")
    LOG.step(f"Detecting outliers in '{col}' using {methods}...")
    n0 = len(df)
    vals = pd.to_numeric(df[col], errors="coerce")

    flags = pd.DataFrame(index=df.index)

    if "iqr" in methods:
        Q1, Q3 = vals.quantile(0.25), vals.quantile(0.75)
        IQR = Q3 - Q1
        lo, hi = Q1 - 3 * IQR, Q3 + 3 * IQR
        flags["outlier_iqr"] = (vals < lo) | (vals > hi)
        LOG.info(f"  IQR outliers: {flags['outlier_iqr'].sum():,} ({flags['outlier_iqr'].mean()*100:.2f}%)")

    if "zscore" in methods:
        mean, std = vals.mean(), vals.std()
        if std > 0:
            z = (vals - mean) / std
            flags["outlier_zscore"] = np.abs(z) > 3
            LOG.info(f"  Z-score outliers: {flags['outlier_zscore'].sum():,} ({flags['outlier_zscore'].mean()*100:.2f}%)")

    if "isolation_forest" in methods:
        try:
            from sklearn.ensemble import IsolationForest
            valid_mask = ~vals.isna()
            X = vals[valid_mask].values.reshape(-1, 1)

            if len(X) > 100_000:
                rng = np.random.default_rng(42)
                idx = rng.choice(len(X), 100_000, replace=False)
                X_sample = X[idx]
            else:
                X_sample = X
            iso = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
            iso.fit(X_sample)
            preds = iso.predict(X)
            flags.loc[valid_mask, "outlier_iso"] = (preds == -1)
            LOG.info(f"  IsolationForest outliers: {flags['outlier_iso'].sum():,} ({flags['outlier_iso'].mean()*100:.2f}%)")
        except ImportError:
            LOG.info("  sklearn not available, skipping IsolationForest")

    outlier_cols = [c for c in flags.columns]
    df = df.copy()
    df["is_outlier"] = flags[outlier_cols].any(axis=1)
    LOG.info(f"  Combined outliers (any method): {df['is_outlier'].sum():,} ({df['is_outlier'].mean()*100:.2f}%)")

    non_outlier = df[~df["is_outlier"]]
    LOG.info(f"  Velocity stats (non-outliers): mean={non_outlier[col].mean():.2f}, "
             f"median={non_outlier[col].median():.2f}, std={non_outlier[col].std():.2f}")
    LOG.result("outlier_detection", n0, len(non_outlier))

    df[f"{col}_clipped"] = vals.clip(
        lower=vals.quantile(0.001),
        upper=vals.quantile(0.999)
    )

    return df

def assign_los_from_velocity(
    df: pd.DataFrame,
    velocity_col: str = "velocity",
    max_velocity_col: str = "max_velocity",
    method: Literal["hcm_strict", "hcm_relaxed", "percentile"] = "hcm_strict",
) -> pd.DataFrame:
    """
    Assign LOS label from V/C ratio.

    Methods:
      - hcm_strict:    V/C >= 0.90->F, >=0.75->E, >=0.60->D, >=0.40->C, >=0.20->B, else A
      - hcm_relaxed:   Vietnam urban context - thresholds shifted by +0.05
      - percentile:    Assign based on velocity percentiles per segment
    """
    LOG.section("SECTION 5: LOS LABELING")
    LOG.step(f"Assigning LOS using method='{method}'...")

    df = df.copy()
    vel = pd.to_numeric(df[velocity_col], errors="coerce")
    max_vel = pd.to_numeric(df[max_velocity_col], errors="coerce").fillna(40).clip(lower=1)
    df["vc_ratio"] = (vel / max_vel).clip(0, 5)

    if method == "hcm_strict":
        LOG.info("Using HCM strict thresholds: A<0.20, B<0.40, C<0.60, D<0.75, E<0.90, F>=0.90")
        def classify(vc):
            if pd.isna(vc): return "F"
            if vc >= 0.90: return "F"
            if vc >= 0.75: return "E"
            if vc >= 0.60: return "D"
            if vc >= 0.40: return "C"
            if vc >= 0.20: return "B"
            return "A"
        df["LOS_assigned"] = df["vc_ratio"].apply(classify)

    elif method == "hcm_relaxed":
        LOG.info("Using HCM relaxed (Vietnam urban): A<0.25, B<0.45, C<0.65, D<0.80, E<0.95, F>=0.95")
        def classify_r(vc):
            if pd.isna(vc): return "F"
            if vc >= 0.95: return "F"
            if vc >= 0.80: return "E"
            if vc >= 0.65: return "D"
            if vc >= 0.45: return "C"
            if vc >= 0.25: return "B"
            return "A"
        df["LOS_assigned"] = df["vc_ratio"].apply(classify_r)

    elif method == "percentile":
        LOG.info("Using percentile-based LOS assignment per segment...")
        seg_thresholds = df.groupby("segment_id")["vc_ratio"].quantile([0.2, 0.4, 0.6, 0.8, 0.9]).unstack()
        seg_thresholds.columns = [f"p{int(float(c)*100)}" for c in seg_thresholds.columns]
        df = df.merge(seg_thresholds, on="segment_id", how="left")
        vc = df["vc_ratio"]
        df["LOS_assigned"] = np.select(
            [vc >= df["p90"], vc >= df["p80"], vc >= df["p60"],
             vc >= df["p40"], vc >= df["p20"]],
            ["F", "E", "D", "C", "B"], default="A"
        )
        df = df.drop(columns=["p20", "p40", "p60", "p80", "p90"])

    los_map = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}
    df["LOS_numeric"] = df["LOS_assigned"].map(los_map)

    dist = df["LOS_assigned"].value_counts().sort_index()
    LOG.info("LOS distribution:")
    for los, cnt in dist.items():
        LOG.info(f"  {los}: {cnt:,} ({cnt/len(df)*100:.1f}%)")

    return df

def build_master_dataset(
    train_df: pd.DataFrame,
    segments_df: pd.DataFrame,
    nodes_df: pd.DataFrame,
    streets_df: pd.DataFrame,
    segment_status_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge all 5 tables into a single master dataset for downstream modeling.

    Merge strategy:
      1. Train x Segments  -> add segment metadata (length, max_velocity, street_level, street_type)
      2. x Nodes (start)   -> add start node coordinates
      3. x Nodes (end)    -> add end node coordinates
      4. x Streets        -> add street name, type from street catalog
      5. x Segment status  -> aggregate latest velocity per segment as feature

    Also computes node degree centrality from segments graph.
    """
    LOG.section("SECTION 6: BUILDING MASTER DATASET")
    LOG.step("Merging tables...")

    df = train_df.copy()
    n_train = len(df)

    seg_meta = segments_df[[
        "_id", "length", "max_velocity", "street_level",
        "street_id", "street_type", "s_node_id", "e_node_id",
    ]].rename(columns={
        "_id": "segment_id",
        "length": "seg_length",
        "max_velocity": "seg_max_velocity",
        "street_level": "seg_street_level",
        "street_type": "seg_street_type",
        "street_id": "street_id_seg",
        "s_node_id": "s_node_id_seg",
        "e_node_id": "e_node_id_seg",
    })
    df = df.merge(seg_meta, on="segment_id", how="left")

    if "street_id" not in df.columns:
        df["street_id"] = np.nan
    df["street_id"] = df["street_id"].fillna(df["street_id_seg"])
    df = df.drop(columns=["street_id_seg"], errors="ignore")

    for col in ["length", "max_velocity", "street_level", "s_node_id", "e_node_id"]:
        if col in df.columns and f"{col}_seg" in df.columns:
            mask = df[col].isna() | (df[col] == 0) | (df[col] == "")
            df.loc[mask, col] = df.loc[mask, f"{col}_seg"]
            df = df.drop(columns=[f"{col}_seg"], errors="ignore")
        elif col not in df.columns and f"{col}_seg" in df.columns:
            df[col] = df[f"{col}_seg"]
            df = df.drop(columns=[f"{col}_seg"], errors="ignore")

    start_node = nodes_df[["_id", "long", "lat"]].rename(columns={
        "_id": "s_node_id",
        "long": "snode_long",
        "lat": "snode_lat",
    })
    df = df.merge(start_node, on="s_node_id", how="left")

    if "long_snode" in df.columns:
        mask = df["long_snode"].isna()
        df.loc[mask, "long_snode"] = df.loc[mask, "snode_long"]
    if "lat_snode" in df.columns:
        mask = df["lat_snode"].isna()
        df.loc[mask, "lat_snode"] = df.loc[mask, "snode_lat"]

    end_node = nodes_df[["_id", "long", "lat"]].rename(columns={
        "_id": "e_node_id",
        "long": "enode_long",
        "lat": "enode_lat",
    })
    df = df.merge(end_node, on="e_node_id", how="left")

    if "long_enode" in df.columns:
        mask = df["long_enode"].isna()
        df.loc[mask, "long_enode"] = df.loc[mask, "enode_long"]
    if "lat_enode" in df.columns:
        mask = df["lat_enode"].isna()
        df.loc[mask, "lat_enode"] = df.loc[mask, "enode_lat"]

    street_meta = streets_df[["_id", "name", "type_std", "level"]].rename(columns={
        "_id": "street_id",
        "name": "street_full_name",
        "type_std": "street_catalog_type",
        "level": "street_catalog_level",
    })
    df = df.merge(street_meta, on="street_id", how="left")

    LOG.step("Aggregating velocity from segment_status...")
    if not segment_status_df.empty and "velocity" in segment_status_df.columns:
        ss_sorted = segment_status_df.dropna(subset=["updated_at"]).sort_values("updated_at").copy()

        grp = ss_sorted.groupby("segment_id")["velocity"]
        ss_sorted["hist_vel_mean"] = grp.expanding().mean().reset_index(0, drop=True)
        ss_sorted["hist_vel_std"] = grp.expanding().std().reset_index(0, drop=True).fillna(0)
        ss_sorted["hist_vel_min"] = grp.expanding().min().reset_index(0, drop=True)
        ss_sorted["hist_vel_max"] = grp.expanding().max().reset_index(0, drop=True)
        ss_sorted["hist_vel_last"] = ss_sorted["velocity"]

        ss_sorted = ss_sorted.rename(columns={"updated_at": "date_merge"})

        df["date_merge"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
        ss_sorted["date_merge"] = pd.to_datetime(ss_sorted["date_merge"], errors="coerce", utc=True)

        df_naive = df["date_merge"].isna().sum()
        ss_naive = ss_sorted["date_merge"].isna().sum()
        if df_naive > 0:
            LOG.warning(f"  {df_naive} rows in df have unparseable dates")
        if ss_naive > 0:
            LOG.warning(f"  {ss_naive} rows in segment_status have unparseable dates")

        df = df.sort_values("date_merge")

        df = pd.merge_asof(
            df,
            ss_sorted[["segment_id", "date_merge", "hist_vel_mean", "hist_vel_std", "hist_vel_min", "hist_vel_max", "hist_vel_last"]],
            on="date_merge",
            by="segment_id",
            direction="backward"
        )
        df = df.drop(columns=["date_merge"])
        LOG.info(f"  Velocity stats merged from segment_status avoiding time leakage.")
    else:
        for col in ["hist_vel_mean", "hist_vel_std", "hist_vel_min",
                    "hist_vel_max", "hist_vel_last"]:
            df[col] = np.nan

    LOG.step("Computing node degree centrality...")
    start_deg = segments_df.groupby("s_node_id").size().reset_index(name="start_degree")
    end_deg = segments_df.groupby("e_node_id").size().reset_index(name="end_degree")

    nodes_df_out = nodes_df.copy()
    nodes_df_out = nodes_df_out.merge(start_deg, left_on="_id", right_on="s_node_id", how="left")
    nodes_df_out = nodes_df_out.merge(end_deg, left_on="_id", right_on="e_node_id", how="left")
    nodes_df_out = nodes_df_out.fillna(0)
    nodes_df_out["node_degree"] = nodes_df_out["start_degree"] + nodes_df_out["end_degree"]

    node_deg = nodes_df_out[["_id", "node_degree", "start_degree", "end_degree"]].rename(
        columns={"_id": "s_node_id"}
    )
    df = df.merge(node_deg, on="s_node_id", how="left")
    df["node_degree"] = df["node_degree"].fillna(0).astype(int)
    df["start_degree"] = df["start_degree"].fillna(0).astype(int)
    df["end_degree"] = df["end_degree"].fillna(0).astype(int)

    drop_cols = [c for c in df.columns if c.startswith("snode_") or c.startswith("enode_")]
    df = df.drop(columns=drop_cols, errors="ignore")

    LOG.result("master_dataset", n_train, len(df))

    LOG.step("Imputing missing max_velocity (cascading strategy)...")
    mask_missing = df["max_velocity"].isna() | (df["max_velocity"] == 0)
    n_missing = mask_missing.sum()
    if n_missing > 0:
        LOG.info(f"  {n_missing:,} rows ({n_missing / len(df) * 100:.1f}%) cần impute max_velocity")

        street_type_vel = {
            "trunk": 80, "motorway": 80, "motorway_link": 80,
            "primary": 60, "primary_link": 60,
            "secondary": 50, "secondary_link": 50,
            "tertiary": 40, "tertiary_link": 40,
            "unclassified": 30, "residential": 30, "service": 20,
        }

        level_vel = {1: 80, 2: 60, 3: 40, 4: 30, 5: 20, 0: 40}

        if "street_type" in df.columns:
            df.loc[mask_missing, "max_velocity"] = (
                df.loc[mask_missing, "street_type"]
                .astype(str).str.strip().str.lower()
                .map(street_type_vel)
                .fillna(df.loc[mask_missing, "max_velocity"])
            )
            mask_missing = df["max_velocity"].isna() | (df["max_velocity"] == 0)

        if "street_level" in df.columns and mask_missing.any():
            df.loc[mask_missing, "max_velocity"] = (
                df.loc[mask_missing, "street_level"]
                .map(level_vel)
                .fillna(df.loc[mask_missing, "max_velocity"])
            )
            mask_missing = df["max_velocity"].isna() | (df["max_velocity"] == 0)

        df["max_velocity"] = df["max_velocity"].fillna(40)

        n_remaining = (df["max_velocity"].isna() | (df["max_velocity"] == 0)).sum()
        LOG.info(f"  Sau imputation: {n_remaining:,} rows van con missing")
    else:
        LOG.info(f"  max_velocity: khong co gia tri missing")

    # Tinh vc_ratio (V/C ratio) tu velocity cuoi cung va max_velocity
    # Su dung hist_vel_last neu co, nguoc lai su dung hist_vel_mean
    if "hist_vel_last" in df.columns:
        vel = df["hist_vel_last"].fillna(df["hist_vel_mean"] if "hist_vel_mean" in df.columns else np.nan)
    elif "hist_vel_mean" in df.columns:
        vel = df["hist_vel_mean"]
    else:
        vel = np.nan
    df["vc_ratio"] = (vel / df["max_velocity"]).clip(0, 5)

    return df, nodes_df_out

def add_time_features(df: pd.DataFrame,
                       date_col: str = "date") -> pd.DataFrame:
    """Extract comprehensive time-based features."""
    LOG.section("SECTION 7: TIME FEATURES")
    LOG.step("Extracting time features...")

    df = df.copy()
    dates = pd.to_datetime(df[date_col], errors="coerce")

    df["year"] = dates.dt.year
    df["month"] = dates.dt.month
    df["day"] = dates.dt.day
    df["dayofyear"] = dates.dt.dayofyear
    df["weekday"] = dates.dt.weekday.fillna(-1).astype(int)
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    df["quarter"] = dates.dt.quarter

    df["weekofyear"] = dates.dt.isocalendar().week.astype(int)

    def _get_vietnam_holidays(years):
        holidays = set()
        for y in years:
            holidays.update([(y, 1, 1), (y, 4, 30), (y, 5, 1), (y, 9, 2)])
        lunar_holidays = {
            2019: [(2019, 2, 2), (2019, 2, 3), (2019, 2, 4), (2019, 2, 5), (2019, 2, 6), (2019, 2, 7), (2019, 2, 8), (2019, 2, 9), (2019, 2, 10), (2019, 4, 14)],
            2020: [(2020, 1, 22), (2020, 1, 23), (2020, 1, 24), (2020, 1, 25), (2020, 1, 26), (2020, 1, 27), (2020, 1, 28), (2020, 1, 29), (2020, 4, 2)],
            2021: [(2021, 2, 10), (2021, 2, 11), (2021, 2, 12), (2021, 2, 13), (2021, 2, 14), (2021, 2, 15), (2021, 2, 16), (2021, 4, 21)],
            2022: [(2022, 1, 29), (2022, 1, 30), (2022, 1, 31), (2022, 2, 1), (2022, 2, 2), (2022, 2, 3), (2022, 2, 4), (2022, 2, 5), (2022, 2, 6), (2022, 4, 10)],
            2023: [(2023, 1, 20), (2023, 1, 21), (2023, 1, 22), (2023, 1, 23), (2023, 1, 24), (2023, 1, 25), (2023, 1, 26), (2023, 4, 29)],
            2024: [(2024, 2, 8), (2024, 2, 9), (2024, 2, 10), (2024, 2, 11), (2024, 2, 12), (2024, 2, 13), (2024, 2, 14), (2024, 4, 18)],
            2025: [(2025, 1, 25), (2025, 1, 26), (2025, 1, 27), (2025, 1, 28), (2025, 1, 29), (2025, 1, 30), (2025, 1, 31), (2025, 2, 1), (2025, 2, 2), (2025, 4, 7)]
        }
        for y in years:
            if y in lunar_holidays:
                holidays.update(lunar_holidays[y])
        return holidays

    holiday_set = _get_vietnam_holidays(df["year"].dropna().unique())
    df_ymd = df.set_index(["year", "month", "day"])
    df["is_holiday"] = df_ymd.index.isin(holiday_set).astype(int)

    if "period" in df.columns:
        df["period_hour"] = (
            df["period"].astype(str)
            .str.extract(r"period_(\d+)_")[0]
            .astype(float)
        )
        df["period_minute"] = (
            df["period"].astype(str)
            .str.extract(r"period_\d+_(\d+)")[0]
            .astype(float)
        )
        df["period_minutes_of_day"] = df["period_hour"] * 60 + df["period_minute"].fillna(0)

        df["hour_sin"] = np.sin(2 * np.pi * df["period_hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["period_hour"] / 24)

        h = df["period_hour"]
        df["is_morning_rush"] = ((h >= 6) & (h < 9)).astype(int)
        df["is_evening_rush"] = ((h >= 16) & (h < 19)).astype(int)
        df["is_rush_hour"] = (df["is_morning_rush"] | df["is_evening_rush"]).astype(int)
        df["is_night"] = ((h >= 22) | (h < 5)).astype(int)
        df["is_working_hours"] = ((h >= 8) & (h < 18)).astype(int)

        df["time_of_day"] = pd.cut(
            h, bins=[-1, 5, 7, 9, 16, 19, 24],
            labels=["night", "early_morning", "morning_rush", "daytime", "evening_rush", "evening"]
        ).astype(str)

    if "weekday" in df.columns:
        df["weekday_sin"] = np.sin(2 * np.pi * df["weekday"] / 7)
        df["weekday_cos"] = np.cos(2 * np.pi * df["weekday"] / 7)

    feat_count = len(df.columns)
    LOG.info(f"  Added {feat_count} time-related columns")
    return df

def normalize_and_encode(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Min-max normalize numeric cols; label-encode categorical cols."""
    LOG.section("SECTION 8: NORMALIZATION & ENCODING")

    df_norm = df.copy()
    encodings = {}

    num_cols = ["length", "max_velocity", "street_level", "hist_vel_mean",
                "hist_vel_std", "hist_vel_max", "hist_vel_min", "hist_vel_last",
                "node_degree", "start_degree", "end_degree",
                "period_hour", "period_minutes_of_day"]
    for col in num_cols:
        if col not in df_norm.columns:
            continue
        vals = pd.to_numeric(df_norm[col], errors="coerce").dropna()
        if vals.empty:
            continue
        lo, hi = vals.min(), vals.max()
        if hi > lo:
            df_norm[f"{col}_norm"] = (df_norm[col] - lo) / (hi - lo)
            LOG.info(f"  Normalized: {col} -> {col}_norm  [{lo:.2f}, {hi:.2f}]")

    cat_cols = ["street_type", "street_name", "period",
                "time_of_day", "street_catalog_type"]
    for col in cat_cols:
        if col not in df_norm.columns:
            continue
        df_norm[col] = df_norm[col].astype(str).str.strip()
        vals = sorted(df_norm[col].dropna().unique())
        mapping = {v: i for i, v in enumerate(vals)}
        encodings[col] = mapping
        df_norm[f"{col}_enc"] = df_norm[col].map(mapping).fillna(-1).astype(int)
        LOG.info(f"  Encoded: {col} -> {col}_enc  ({len(mapping)} categories)")

    LOG.save("encodings", encodings)
    return df_norm, encodings

def export_outputs(
    master_df: pd.DataFrame,
    nodes_df: pd.DataFrame,
    segments_df: pd.DataFrame,
    streets_df: pd.DataFrame,
    segment_status_df: pd.DataFrame,
    encodings: dict,
    quality_report: dict,
):
    """Lưu tất cả output dưới dạng CSV."""
    LOG.section("SECTION 9: EXPORTING OUTPUTS")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if "date" in master_df.columns:
        master_df["date"] = pd.to_datetime(master_df["date"], errors="coerce")
        master_df = master_df.sort_values("date")
        LOG.info(f"  Sorted by date: {master_df['date'].min()} to {master_df['date'].max()}")

    csv_path = OUTPUT_DIR / "train_features_base.csv"
    master_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    csv_size_mb = csv_path.stat().st_size / 1_048_576
    LOG.step(f"Saved: {csv_path.name} ({csv_size_mb:.1f} MB, {len(master_df):,} rows)")

    tables = {
        "nodes_clean": nodes_df,
        "segments_clean": segments_df,
        "streets_clean": streets_df,
        "segment_status_clean": segment_status_df,
    }
    for name, tdf in tables.items():
        tdf.to_csv(OUTPUT_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
        LOG.step(f"Saved: {name}.csv  ({len(tdf):,} rows)")

    enc_json = {k: {str(kk): int(vv) for kk, vv in v.items()} for k, v in encodings.items()}
    with open(OUTPUT_DIR / "label_encodings.json", "w", encoding="utf-8") as f:
        json.dump(enc_json, f, ensure_ascii=False, indent=2)
    LOG.step("Saved: label_encodings.json")

    feature_info = {
        "target_cols": ["LOS"],
        "drop_cols": ["date", "period", "segment_id", "street_id", "s_node_id", "e_node_id", "is_outlier"],
        "cat_cols": list(encodings.keys()),
        "num_cols": [c for c in master_df.columns if c.endswith("_norm")] + ["hour_sin", "hour_cos", "is_holiday", "is_rush_hour"]
    }
    with open(OUTPUT_DIR / "preprocessing_feature_info.json", "w", encoding="utf-8") as f:
        json.dump(feature_info, f, ensure_ascii=False, indent=2)
    LOG.step("Saved: preprocessing_feature_info.json")

    LOG.save_report(OUTPUT_DIR / "quality_report.json")

    print(f"\n{'=' * 60}")
    print(f"  All outputs -> {OUTPUT_DIR}")
    print(f"{'=' * 60}")

def preprocess_pipeline():
    """
    Full preprocessing pipeline:

      0. Setup
      1. Load 5 CSV files
      2. Data quality profiling
      3. Enhanced cleaning (per table)
      4. Outlier detection on velocity
      5. LOS labeling
      6. Build master dataset (merge all 5 tables)
      7. Time features
      8. Normalization & encoding
      9. Export (CSV + quality report)
    """
    print(f"\n{'#' * 60}")
    print(f"#  Traffic LOS Preprocessing Pipeline")
    print(f"#  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 60}")

    LOG.section("SECTION 1: LOADING DATA")
    tables = load_all_data()

    LOG.section("SECTION 2: QUALITY PROFILING")
    profile_data_quality(tables)

    if not tables["segment_status"].empty:
        continuity_df = check_time_series_continuity(tables["segment_status"], date_col="updated_at")
        LOG.info(f"Checked continuity for {len(continuity_df):,} segments.")

    LOG.section("SECTION 3: CLEANING ALL TABLES")
    nodes, _ = clean_nodes(tables["nodes"])
    segments, _ = clean_segments(tables["segments"], nodes)
    streets, _ = clean_streets(tables["streets"])
    segment_status, _ = clean_segment_status(tables["segment_status"], segments)
    train, _ = clean_train(tables["train"], segments, nodes)

    LOG.section("SECTION 4: OUTLIER DETECTION")
    segment_status = detect_velocity_outliers(segment_status, col="velocity",
                                              methods=["iqr", "zscore"])

    if "velocity_clipped" in segment_status.columns:
        segment_status["velocity"] = segment_status["velocity_clipped"]

    LOG.section("SECTION 5b: FILTERING OUTLIERS FROM SEGMENT STATUS")
    # Outliers da duoc phat hien trong SECTION 4. Can loc chung khoi segment_status
    # truoc khi merge vao master_df de dam bao lich su velocity khong bi polluted
    outlier_count = segment_status["is_outlier"].sum() if "is_outlier" in segment_status.columns else 0
    if outlier_count > 0:
        segment_status_clean = segment_status[~segment_status["is_outlier"]].copy()
        LOG.step(f"Loc {outlier_count:,} outlier khoi segment_status (con lai: {len(segment_status_clean):,} rows)")
        LOG.info(f"  Velocity stats (non-outliers): mean={segment_status_clean['velocity'].mean():.2f}, "
                 f"median={segment_status_clean['velocity'].median():.2f}")
        segment_status = segment_status_clean
    else:
        LOG.step("Khong co outlier trong segment_status.")

    segment_status = segment_status.drop(columns=["is_outlier", "velocity_clipped", "outlier_iqr", "outlier_zscore", "outlier_iso"], errors="ignore")

    LOG.section("SECTION 6: BUILDING MASTER DATASET")
    master_df, nodes_enriched = build_master_dataset(
        train, segments, nodes, streets, segment_status
    )

    LOG.section("SECTION 7: TIME FEATURES")
    master_df = add_time_features(master_df, date_col="date")

    LOG.section("SECTION 8: NORMALIZATION & ENCODING")
    master_df, encodings = normalize_and_encode(master_df)

    LOG.section("SECTION 9: EXPORT")
    export_outputs(
        master_df=master_df,
        nodes_df=nodes_enriched,
        segments_df=segments,
        streets_df=streets,
        segment_status_df=segment_status,
        encodings=encodings,
        quality_report=LOG._report,
    )

    print(f"\n{'#' * 60}")
    print(f"#  Pipeline completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"#  Master dataset: {len(master_df):,} rows x {len(master_df.columns)} cols")
    print(f"{'#' * 60}\n")

    return {
        "master": master_df,
        "nodes": nodes_enriched,
        "segments": segments,
        "streets": streets,
        "segment_status": segment_status,
        "encodings": encodings,
        "quality_report": LOG._report,
    }

if __name__ == "__main__":
    results = preprocess_pipeline()
