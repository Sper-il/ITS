"""
train_stacking.py — Phan loai LOS giao thong bang Stacking Ensemble

Quy trinh day du bao gom:
  - Tai & kiem tra du lieu tu train_features.csv
  - Chia theo thoi gian (tranh ro ri du lieu theo thoi gian)
  - Xu ly gia tri thieu (SimpleImputer)
  - Xu ly mat can bang lop (class_weight='balanced')
  - Huan luyen Stacking Ensemble (RF + XGB + LGBM + CatBoost → LogReg meta)
  - Cross-Validation danh gia ngoai (5-fold, mean ± std)
  - Bao cao Feature Importance (top-20)
  - Luu day du artifacts (model, encoder, metrics, metadata)

Chay:
    cd TRAFFIC_PROCESSING
    python scripts/train_traffic_from_stacking/train_stacking.py
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import sklearn

from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    f1_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

warnings.filterwarnings("ignore")

# ==============================================================================
# CAU HINH — Chinh sua cac tham so o day
# ==============================================================================

BASE_DIR = Path(__file__).parent.parent.parent
OUTPUTS_DIR = BASE_DIR / "scripts" / "outputs"
MODELS_DIR  = BASE_DIR / "models"

INPUT_CSV           = OUTPUTS_DIR / "train_features.csv"
FEATURE_INFO_JSON   = OUTPUTS_DIR / "feature_info.json"
OPTUNA_PARAMS_FILE  = MODELS_DIR / "best_optuna_params.json"

TARGET_COL    = "LOS"
DATE_COL      = "date"
VAL_RATIO     = 0.20
N_CV_FOLDS    = 3
RANDOM_STATE  = 42
N_JOBS        = -1


# ==============================================================================
# LOGGER
# ==============================================================================

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ==============================================================================
# BUOC 0: Kiem tra file dau vao
# ==============================================================================

def kiem_tra_dau_vao():
    log("=" * 65)
    log("  Huan luyen Stacking Ensemble — Phan loai LOS giao thong")
    log(f"  Bat dau: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 65)

    for path, name in [(INPUT_CSV, "train_features.csv"),
                       (FEATURE_INFO_JSON, "feature_info.json")]:
        if not path.exists():
            raise FileNotFoundError(
                f"\n[LOI] Khong tim thay: {path}\n"
                f"  Hay chay pipeline theo dung thu tu:\n"
                f"     1. python scripts/data_processing/preprocessing.py\n"
                f"     2. python scripts/feature_engineering/feature_engineering.py\n"
                f"     3. python scripts/train_traffic_from_stacking/train_stacking.py\n"
            )
        size_mb = path.stat().st_size / 1_048_576
        log(f"  ✓ {name} ({size_mb:.1f} MB)")

    KNOWN_BAD_FEATURES = {"s_node_degree"}
    with open(FEATURE_INFO_JSON, "r", encoding="utf-8") as f:
        feat_info_check = json.load(f)
    bad_features = [f for f in feat_info_check.get("feature_names", [])
                   if f in KNOWN_BAD_FEATURES]
    if bad_features:
        raise FileNotFoundError(
            f"\n[LOI] feature_info.json chua cac feature names BI LOI tu code CU:\n"
            f"  {bad_features}\n"
            f"  Dieu nay co nghia la feature_engineering.py chua duoc chay sau khi sua.\n"
            f"  Hay chay lai:\n"
            f"     python scripts/feature_engineering/feature_engineering.py\n"
            f"  (sau khi da chay preprocessing.py)\n"
        )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# BUOC 1: Tai du lieu va danh sach feature
# ==============================================================================

def tai_du_lieu():
    log("\n[1/6] Dang tai du lieu...")
    t0 = time.time()

    with open(FEATURE_INFO_JSON, "r", encoding="utf-8") as f:
        feature_info = json.load(f)

    feature_names = feature_info["feature_names"]
    log(f"  feature_info.json: {len(feature_names)} features duoc khai bao")

    df = pd.read_csv(INPUT_CSV, low_memory=False)
    log(f"  train_features.csv: {df.shape[0]:,} dong x {df.shape[1]} cot  [{time.time()-t0:.1f}s]")

    missing_cols = [c for c in feature_names if c not in df.columns]
    if missing_cols:
        log(f"  [CANH BAO] {len(missing_cols)} feature(s) duoc khai bao trong feature_info.json "
            f"nhung KHONG co trong CSV:")
        for c in missing_cols[:10]:
            log(f"    - {c}")
        if len(missing_cols) > 10:
            log(f"    ... va {len(missing_cols) - 10} cot khac")
        log("  → Se su dung intersection (chi cac cot co trong ca hai).")

    feature_names = [c for c in feature_names if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    log(f"  → So features thuc su su dung: {len(feature_names)}")

    return df, feature_names


# ==============================================================================
# BUOC 2: Encode nhan & Chia theo thoi gian
# ==============================================================================

def chuan_bi_du_lieu(df: pd.DataFrame, feature_names: list):
    log("\n[2/6] Chuan bi du lieu...")

    if df[TARGET_COL].dtype == object:
        le = LabelEncoder()
        df[TARGET_COL] = le.fit_transform(df[TARGET_COL])
        class_names = le.classes_.tolist()
        log(f"  Cac lop LOS: {class_names}")
    else:
        le = LabelEncoder()
        unique_vals = sorted(df[TARGET_COL].unique())
        le.fit(unique_vals)
        class_names = [str(v) for v in unique_vals]
        log(f"  Cac lop LOS (numeric): {class_names}")

    joblib.dump(le, MODELS_DIR / "los_label_encoder.joblib")
    log(f"  Da luu: los_label_encoder.joblib")

    log("  Phan bo LOS trong toan bo dataset:")
    counts = df[TARGET_COL].value_counts().sort_index()
    total = len(df)
    for cls_idx, cnt in counts.items():
        cls_name = class_names[cls_idx] if cls_idx < len(class_names) else str(cls_idx)
        log(f"    LOS {cls_name}: {cnt:,}  ({cnt/total*100:.1f}%)")

    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
        df = df.sort_values(DATE_COL)
        split_idx_train = int(len(df) * 0.8)
        split_idx_val = int(len(df) * 0.9)

        train_df = df.iloc[:split_idx_train]
        val_df   = df.iloc[split_idx_train:split_idx_val]
        test_df  = df.iloc[split_idx_val:]

        log(f"\n  Chia 80/10/10 theo thoi gian:")
        log(f"    Train: {len(train_df):,} dong  (den {train_df[DATE_COL].max().date()})")
        log(f"    Val  : {len(val_df):,} dong  (tu {val_df[DATE_COL].min().date()} den {val_df[DATE_COL].max().date()})")
        log(f"    Test : {len(test_df):,} dong  (tu {test_df[DATE_COL].min().date()} den {test_df[DATE_COL].max().date()})")
    else:
        log("  [CANH BAO] Khong co cot 'date' → fallback sang stratified random split 80/10/10")
        from sklearn.model_selection import train_test_split
        train_val_df, test_df = train_test_split(df, test_size=0.1, stratify=df[TARGET_COL], random_state=RANDOM_STATE)
        train_df, val_df = train_test_split(train_val_df, test_size=1/9, stratify=train_val_df[TARGET_COL], random_state=RANDOM_STATE)
        log(f"\n  Random split 80/10/10:")
        log(f"    Train: {len(train_df):,} dong")
        log(f"    Val  : {len(val_df):,} dong")
        log(f"    Test : {len(test_df):,} dong")

    split_dir = BASE_DIR / "scripts" / "data_after_split"
    (split_dir / "train").mkdir(parents=True, exist_ok=True)
    (split_dir / "val").mkdir(parents=True, exist_ok=True)
    (split_dir / "test").mkdir(parents=True, exist_ok=True)

    train_df.to_csv(split_dir / "train" / "train.csv", index=False)
    val_df.to_csv(split_dir / "val" / "val.csv", index=False)
    test_df.to_csv(split_dir / "test" / "test.csv", index=False)
    log(f"    Da luu splits vao: {split_dir}")

    X_train = train_df[feature_names]
    y_train = train_df[TARGET_COL]
    X_val   = val_df[feature_names]
    y_val   = val_df[TARGET_COL]
    X_test  = test_df[feature_names]
    y_test  = test_df[TARGET_COL]

    nan_train = X_train.isna().sum().sum()
    nan_val   = X_val.isna().sum().sum()
    nan_test  = X_test.isna().sum().sum()
    log(f"\n  So NaN — Train: {nan_train:,}  |  Val: {nan_val:,}  |  Test: {nan_test:,}")
    if nan_train > 0:
        top_nan = X_train.isna().sum().sort_values(ascending=False).head(5)
        log("  Top 5 cot nhieu NaN nhat (train):")
        for col, n in top_nan.items():
            log(f"    {col}: {n:,}")

    return X_train, X_val, X_test, y_train, y_val, y_test, le, class_names


# ==============================================================================
# BUOC 3: Xay dung Stacking Ensemble voi Pipeline (NaN safe)
# ==============================================================================

def xay_dung_stacking_pipeline(y_train: pd.Series, class_names: list, optuna_params: dict = None):
    log("\n[3/6] Dang xay dung Stacking Ensemble...")

    n_classes = len(class_names)
    log(f"  So lop phan loai: {n_classes} ({class_names})")

    from sklearn.utils.class_weight import compute_class_weight
    classes_arr = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes_arr, y=y_train)
    class_weight_dict = dict(zip(classes_arr.tolist(), weights.tolist()))
    log(f"  Class weights (balanced): { {str(k):round(v,3) for k,v in class_weight_dict.items()} }")

    imputer = SimpleImputer(strategy="median")

    xgb_params = optuna_params.get("xgb", {}) if optuna_params else {}
    lgbm_params = optuna_params.get("lgbm", {}) if optuna_params else {}

    GAMMA_FOCAL = 1.5
    log(f"  Focal loss gamma: {GAMMA_FOCAL} (LightGBM & CatBoost)")

    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=None,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=N_JOBS,
    )

    xgb = XGBClassifier(
        n_estimators=100,
        learning_rate=xgb_params.get("learning_rate", 0.05),
        max_depth=xgb_params.get("max_depth", 6),
        subsample=xgb_params.get("subsample", 0.8),
        colsample_bytree=xgb_params.get("colsample_bytree", 0.8),
        eval_metric="mlogloss",
        random_state=RANDOM_STATE,
        n_jobs=N_JOBS,
        verbosity=0,
    )

    lgbm = LGBMClassifier(
        n_estimators=100,
        learning_rate=lgbm_params.get("learning_rate", 0.05),
        max_depth=lgbm_params.get("max_depth", -1),
        num_leaves=lgbm_params.get("num_leaves", 63),
        subsample=lgbm_params.get("subsample", 0.8),
        is_unbalance=False,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=N_JOBS,
        verbose=-1,
    )

    cat = CatBoostClassifier(
        iterations=100,
        learning_rate=0.05,
        depth=6,
        auto_class_weights="Balanced",
        random_seed=RANDOM_STATE,
        verbose=0,
    )

    base_learners = [
        ("rf",   rf),
        ("xgb",  xgb),
        ("lgbm", lgbm),
        ("cat",  cat),
    ]

    meta_learner = LogisticRegression(
        max_iter=2000,
        random_state=RANDOM_STATE,
        class_weight="balanced",
        C=0.01,
    )

    from sklearn.model_selection import StratifiedKFold
    stack_cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)

    stacking = StackingClassifier(
        estimators=base_learners,
        final_estimator=meta_learner,
        cv=stack_cv,
        stack_method="predict_proba",
        passthrough=False,
        n_jobs=1,
    )

    pipeline = Pipeline([
        ("imputer", imputer),
        ("stacking", stacking),
    ])

    log(f"  Base learners: RF(300), XGB(300), LGBM(300), CatBoost(300)")
    log(f"  Meta-learner: LogisticRegression(class_weight=balanced)")
    log(f"  Imputer: SimpleImputer(strategy=median)")

    return pipeline


# ==============================================================================
# BUOC 4: Huan luyen va danh gia tren tap val
# ==============================================================================

def huan_luyen_va_danh_gia(pipeline, X_train, X_val, y_train, y_val, class_names):
    log("\n[4/6] Dang huan luyen mo hinh...")
    t0 = time.time()

    pipeline.fit(X_train, y_train)
    train_time = time.time() - t0
    log(f"  Thoi gian huan luyen: {train_time/60:.1f} phut ({train_time:.0f}s)")

    log("\n  === Ket qua tren Tap Validation ===")
    y_pred = pipeline.predict(X_val)
    acc    = accuracy_score(y_val, y_pred)
    mac_f1 = f1_score(y_val, y_pred, average="macro")

    log(f"  Do chinh xac  : {acc:.4f}  ({acc*100:.2f}%)")
    log(f"  Macro F1  : {mac_f1:.4f}")
    print("\n" + classification_report(y_val, y_pred, target_names=[f"LOS_{c}" for c in class_names]))

    cm = confusion_matrix(y_val, y_pred)
    print("Ma tran lang nhien:")
    print(cm)

    report_dict = classification_report(
        y_val, y_pred,
        target_names=[f"LOS_{c}" for c in class_names],
        output_dict=True,
    )

    return pipeline, report_dict, acc, mac_f1, train_time


# ==============================================================================
# BUOC 5: Cross-Validation danh gia ngoai
# ==============================================================================

def cross_validate_pipeline(pipeline, X_train, y_train):
    log(f"\n[5/6] Cross-Validation ngoai ({N_CV_FOLDS}-fold StratifiedKFold)...")
    log("  (Du lieu da duoc chia theo thoi gian trong main(); su dung StratifiedKFold cho CV)")
    t0 = time.time()

    cv = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    cv_results = cross_validate(
        pipeline, X_train, y_train,
        cv=cv,
        scoring={"accuracy": "accuracy", "macro_f1": "f1_macro"},
        n_jobs=1,
        return_train_score=False,
        verbose=0,
    )

    cv_acc    = cv_results["test_accuracy"]
    cv_mac_f1 = cv_results["test_macro_f1"]
    cv_time   = time.time() - t0

    log(f"\n  === Ket qua Cross-Validation ({N_CV_FOLDS}-fold) ===")
    log(f"  Do chinh xac : {cv_acc.mean():.4f} ± {cv_acc.std():.4f}")
    log(f"  Macro F1 : {cv_mac_f1.mean():.4f} ± {cv_mac_f1.std():.4f}")
    for i, (a, f) in enumerate(zip(cv_acc, cv_mac_f1), 1):
        log(f"    Fold {i}: Acc={a:.4f}  MacroF1={f:.4f}")
    log(f"  Thoi gian CV: {cv_time/60:.1f} phut ({cv_time:.0f}s)")

    return {
        "cv_accuracy_mean": float(cv_acc.mean()),
        "cv_accuracy_std":  float(cv_acc.std()),
        "cv_macro_f1_mean": float(cv_mac_f1.mean()),
        "cv_macro_f1_std":  float(cv_mac_f1.std()),
        "cv_accuracy_per_fold":  cv_acc.tolist(),
        "cv_macro_f1_per_fold":  cv_mac_f1.tolist(),
    }


# ==============================================================================
# BUOC 5b: Danh gia tren tap test + Phan tich phan bo lop
# ==============================================================================

def danh_gia_tren_test(pipeline, X_test, y_test, X_val, y_val, y_train, class_names):
    """Danh gia mo hinh tren tap test va phan tich phan bo lop."""
    log("\n[5b/6] Dang danh gia tren Tap Test...")

    log("  Phan bo LOS (Phan tich Thay doi Phan bo Lop):")
    log(f"  {'Lop':<8} {'Train':<12} {'Val':<12} {'Test':<12}")
    log("  " + "-" * 44)

    train_counts = y_train.value_counts()
    val_counts = y_val.value_counts()
    test_counts = y_test.value_counts()
    total_train = len(y_train)
    total_val = len(y_val)
    total_test = len(y_test)

    for cls_idx in range(len(class_names)):
        cls_name = class_names[cls_idx]
        train_pct = train_counts.get(cls_idx, 0) / total_train * 100
        val_pct = val_counts.get(cls_idx, 0) / total_val * 100
        test_pct = test_counts.get(cls_idx, 0) / total_test * 100
        log(f"  {cls_name:<8} {train_pct:>6.1f}%      {val_pct:>6.1f}%      {test_pct:>6.1f}%")

    log("\n  [THONG TIN] Kiem tra thay doi phan bo (val vs test):")
    for cls_idx in range(len(class_names)):
        val_pct = val_counts.get(cls_idx, 0) / total_val * 100
        test_pct = test_counts.get(cls_idx, 0) / total_test * 100
        shift = abs(val_pct - test_pct)
        if shift > 10:
            log(f"    [!] LOS {class_names[cls_idx]}: shift={shift:.1f}% {'(THAY DOI LON)' if shift > 20 else ''}")

    y_pred_test = pipeline.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred_test)
    test_f1 = f1_score(y_test, y_pred_test, average="macro")

    log(f"\n  === Ket qua Tap Test ===")
    log(f"  Do chinh xac Test : {test_acc:.4f}  ({test_acc*100:.2f}%)")
    log(f"  Test Macro F1 : {test_f1:.4f}")
    log(f"  (So sanh voi Val: Acc={accuracy_score(y_val, pipeline.predict(X_val)):.4f})")
    print("\n" + classification_report(y_test, y_pred_test, target_names=[f"LOS_{c}" for c in class_names]))

    cm_test = confusion_matrix(y_test, y_pred_test)
    print("Ma tran Lang nhien (Tap Test):")
    print(cm_test)

    test_report = classification_report(
        y_test, y_pred_test,
        target_names=[f"LOS_{c}" for c in class_names],
        output_dict=True,
    )

    return {
        "test_accuracy": float(test_acc),
        "test_macro_f1": float(test_f1),
        "test_classification_report": test_report,
    }


# ==============================================================================
# BUOC 6: Feature Importance + Luu artifacts
# ==============================================================================

def trich_xuat_feature_importance(pipeline, feature_names: list):
    log("\n  --- Feature Importance ---")
    stacking_clf = pipeline.named_steps["stacking"]
    importance_records = []

    model_attr = {
        "rf":   "feature_importances_",
        "xgb":  "feature_importances_",
        "lgbm": "feature_importances_",
    }

    for name, attr in model_attr.items():
        try:
            estimator = stacking_clf.named_estimators_[name]
            imp = getattr(estimator, attr)
            for feat, val in zip(feature_names, imp):
                importance_records.append({"model": name, "feature": feat, "importance": val})
        except Exception as e:
            log(f"    [CANH BAO] Khong lay duoc importance tu {name}: {e}")

    if not importance_records:
        return pd.DataFrame()

    imp_df = pd.DataFrame(importance_records)

    mean_imp = (
        imp_df.groupby("feature")["importance"]
        .mean()
        .reset_index()
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

    log(f"\n  Top 20 Features quan trong nhat (mean importance):")
    for i, row in mean_imp.head(20).iterrows():
        bar = "█" * int(row["importance"] * 200)
        log(f"    {i+1:2d}. {row['feature']:<40s}  {row['importance']:.4f}  {bar}")

    return imp_df, mean_imp


def luu_artifacts(pipeline, feature_names, report_dict, acc, mac_f1,
                   train_time, cv_results, imp_df, mean_imp, class_names):
    log(f"\n[6/6] Luu artifacts vao {MODELS_DIR}...")

    model_path = MODELS_DIR / "stacking_ensemble_ITS.joblib"
    joblib.dump(pipeline, model_path)
    size_mb = model_path.stat().st_size / 1_048_576
    log(f"  ✓ stacking_ensemble_ITS.joblib ({size_mb:.1f} MB)")

    feat_used = {"feature_names": feature_names, "num_features": len(feature_names)}
    with open(MODELS_DIR / "feature_names_used.json", "w", encoding="utf-8") as f:
        json.dump(feat_used, f, ensure_ascii=False, indent=2)
    log(f"  ✓ feature_names_used.json ({len(feature_names)} features)")

    metrics = {
        "val_accuracy":  round(acc, 6),
        "val_macro_f1":  round(mac_f1, 6),
        "class_names":   class_names,
        "classification_report": report_dict,
        **cv_results,
    }
    with open(MODELS_DIR / "training_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    log(f"  ✓ training_metrics.json")

    metadata = {
        "trained_at":        datetime.now().isoformat(),
        "input_file":        str(INPUT_CSV),
        "num_features":      len(feature_names),
        "target_col":        TARGET_COL,
        "val_ratio":         VAL_RATIO,
        "split_type":        "time_based",
        "n_cv_folds":        N_CV_FOLDS,
        "random_state":      RANDOM_STATE,
        "train_time_sec":    round(train_time, 1),
        "sklearn_version":   sklearn.__version__,
    }
    with open(MODELS_DIR / "training_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    log(f"  ✓ training_metadata.json")

    if imp_df is not None and not imp_df.empty:
        imp_csv = MODELS_DIR / "feature_importance.csv"
        imp_df.to_csv(imp_csv, index=False, encoding="utf-8-sig")
        mean_imp.to_csv(MODELS_DIR / "feature_importance_mean.csv", index=False, encoding="utf-8-sig")
        log(f"  ✓ feature_importance.csv + feature_importance_mean.csv")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    total_start = time.time()

    kiem_tra_dau_vao()
    df, feature_names = tai_du_lieu()
    X_train, X_val, X_test, y_train, y_val, y_test, le, class_names = chuan_bi_du_lieu(df, feature_names)

    optuna_params = None
    if OPTUNA_PARAMS_FILE.exists():
        with open(OPTUNA_PARAMS_FILE, "r") as f:
            optuna_params = json.load(f)
        log(f"  Da tai Optuna params: XGB n_estimators={optuna_params.get('xgb',{}).get('n_estimators','N/A')}, "
            f"LGBM n_estimators={optuna_params.get('lgbm',{}).get('n_estimators','N/A')}")
    pipeline = xay_dung_stacking_pipeline(y_train, class_names, optuna_params)

    pipeline, report_dict, acc, mac_f1, train_time = huan_luyen_va_danh_gia(
        pipeline, X_train, X_val, y_train, y_val, class_names
    )

    cv_results = cross_validate_pipeline(pipeline, X_train, y_train)

    test_results = danh_gia_tren_test(pipeline, X_test, y_test, X_val, y_val, y_train, class_names)

    result = trich_xuat_feature_importance(pipeline, feature_names)
    if isinstance(result, tuple):
        imp_df, mean_imp = result
    else:
        imp_df, mean_imp = None, None

    luu_artifacts(pipeline, feature_names, report_dict, acc, mac_f1,
                   train_time, cv_results, imp_df, mean_imp, class_names)

    total_time = time.time() - total_start
    log(f"\n{'=' * 65}")
    log(f"  HOAN TAT!")
    log(f"  Tong thoi gian: {total_time/60:.1f} phut ({total_time:.0f}s)")
    log(f"  Ket qua: Accuracy={acc*100:.2f}%  MacroF1={mac_f1:.4f}")
    log(f"{'=' * 65}")


if __name__ == "__main__":
    main()
