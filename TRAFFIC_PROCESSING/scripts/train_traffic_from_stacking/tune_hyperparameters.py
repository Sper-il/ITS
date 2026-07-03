"""
tune_hyperparameters.py — Tối ưu hóa siêu tham số (Optuna) cho các base models của ITS LOS.
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import optuna
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

optuna.logging.set_verbosity(optuna.logging.WARNING)

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).parent.parent.parent
OUTPUTS_DIR = BASE_DIR / "scripts" / "outputs"
MODELS_DIR = BASE_DIR / "models"
INPUT_CSV = OUTPUTS_DIR / "train_features.csv"
FEATURE_INFO_JSON = OUTPUTS_DIR / "feature_info.json"
TARGET_COL = "LOS"
N_TRIALS = 30 # Cho luận văn, thường 50-100, nhưng 30 là vừa đủ để chạy nhanh

def load_data():
    with open(FEATURE_INFO_JSON, "r", encoding="utf-8") as f:
        feature_names = json.load(f)["feature_names"]
    df = pd.read_csv(INPUT_CSV, low_memory=False)
    feature_names = [c for c in feature_names if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date")
    
    le = LabelEncoder()
    df[TARGET_COL] = le.fit_transform(df[TARGET_COL].astype(str))
    
    X = df[feature_names]
    y = df[TARGET_COL]
    
    # Điền giá trị thiếu (impute missing)
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=feature_names)
    
    return X_imputed, y

def objective_xgb(trial, X, y):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 500),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "eval_metric": "mlogloss",
        "n_jobs": 1,
        "random_state": 42
    }
    tscv = TimeSeriesSplit(n_splits=3)
    scores = []
    for train_idx, val_idx in tscv.split(X):
        X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
        X_va, y_va = X.iloc[val_idx], y.iloc[val_idx]
        
        sample_weight = compute_sample_weight("balanced", y_tr)
        model = XGBClassifier(**params)
        model.fit(X_tr, y_tr, sample_weight=sample_weight)
        preds = model.predict(X_va)
        scores.append(f1_score(y_va, preds, average="macro"))
    return np.mean(scores)

def objective_lgbm(trial, X, y):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 500),
        "max_depth": trial.suggest_int("max_depth", -1, 15),
        "num_leaves": trial.suggest_int("num_leaves", 20, 150),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "is_unbalance": True,
        # Lưu ý: class_weight="balanced" sẽ thừa khi dùng is_unbalance=True
        # (cả hai đều bảo LGBM bù đắp cho sự mất cân bằng lớp). is_unbalance=True là đủ.
        "n_jobs": 1,
        "random_state": 42,
        "verbose": -1
    }
    tscv = TimeSeriesSplit(n_splits=3)
    scores = []
    for train_idx, val_idx in tscv.split(X):
        X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
        X_va, y_va = X.iloc[val_idx], y.iloc[val_idx]
        
        sample_weight = compute_sample_weight("balanced", y_tr)
        model = LGBMClassifier(**params)
        model.fit(X_tr, y_tr, sample_weight=sample_weight)
        preds = model.predict(X_va)
        scores.append(f1_score(y_va, preds, average="macro"))
    return np.mean(scores)

def main():
    print("="*60)
    print("  Tối ưu hóa Siêu tham số Optuna cho Mô hình Base của Stacking")
    print("="*60)
    
    if not INPUT_CSV.exists():
        print(f"[LỖI] Không tìm thấy file: {INPUT_CSV}")
        sys.exit(1)

    # P0-1 FIX: Kiểm tra feature_info.json cho các feature name lỗi/thừa
    KNOWN_BAD_FEATURES = {"s_node_degree"}  # Thực sự lỗi: truy cập cột không tồn tại
    # Lưu ý: *_x / *_y là các feature tương tác hợp lệ, KHÔNG phải lỗi
    if FEATURE_INFO_JSON.exists():
        with open(FEATURE_INFO_JSON, "r", encoding="utf-8") as f:
            feat_info = json.load(f)
        bad = [f for f in feat_info.get("feature_names", []) if f in KNOWN_BAD_FEATURES]
        if bad:
            print(f"[LỖI] feature_info.json chứa các feature lỗi: {bad}")
            print(f"  → Chạy lại: python scripts/feature_engineering/feature_engineering.py")
            sys.exit(1)
        
    X, y = load_data()
    best_params = {}
    
    # XGBoost
    print("\n--- Đang tối ưu XGBoost ---")
    study_xgb = optuna.create_study(direction="maximize")
    study_xgb.optimize(lambda trial: objective_xgb(trial, X, y), n_trials=N_TRIALS)
    best_params["xgb"] = study_xgb.best_params
    print("Tham số XGB tốt nhất:", study_xgb.best_params)
    
    # LightGBM
    print("\n--- Đang tối ưu LightGBM ---")
    study_lgbm = optuna.create_study(direction="maximize")
    study_lgbm.optimize(lambda trial: objective_lgbm(trial, X, y), n_trials=N_TRIALS)
    best_params["lgbm"] = study_lgbm.best_params
    print("Tham số LGBM tốt nhất:", study_lgbm.best_params)
    
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODELS_DIR / "best_optuna_params.json", "w") as f:
        json.dump(best_params, f, indent=2)
    print(f"\nĐã lưu các tham số tối ưu vào {MODELS_DIR / 'best_optuna_params.json'}")

if __name__ == "__main__":
    main()
