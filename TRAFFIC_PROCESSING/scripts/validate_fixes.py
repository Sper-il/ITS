"""
Script kiểm tra nhanh các bản sửa lỗi cho pipeline Traffic LOS của ITS.
Chạy script này để xác minh tất cả các bản sửa lỗi hoạt động mà không cần đợi CV đầy đủ.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.metrics import classification_report, accuracy_score, f1_score, confusion_matrix
import joblib

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "scripts" / "outputs"

print("=" * 60)
print("  ITS Traffic LOS - Kiểm tra nhanh")
print("=" * 60)

# 1. Kiểm tra model có tồn tại không
 model_path = MODELS_DIR / "stacking_ensemble_ITS.joblib"
if model_path.exists():
    print(f"✓ Model tồn tại: {model_path.stat().st_size / 1_048_576:.1f} MB")
else:
    print("✗ Không tìm thấy Model!")
    exit(1)

# 2. Nạp dữ liệu - sử dụng feature names từ model đã train
print("\n[1] Đang nạp dữ liệu...")
# Sử dụng feature_names từ model đã train (92 đặc trưng) không phải feature_info.json đầy đủ (149)
saved_features = json.load(open(MODELS_DIR / "feature_names_used.json"))
feature_names = saved_features["feature_names"]
print(f"  Sử dụng {len(feature_names)} đặc trưng từ cấu hình đã lưu của model")

df = pd.read_csv(OUTPUTS_DIR / "train_features.csv", low_memory=False)
print(f"  Dữ liệu: {df.shape[0]:,} dòng x {df.shape[1]} cột")

# Kiểm tra đặc trưng nào thực sự có trong dữ liệu
available = [f for f in feature_names if f in df.columns]
missing = [f for f in feature_names if f not in df.columns]
if missing:
    print(f"  CẢNH BÁO: Thiếu {len(missing)} đặc trưng trong CSV: {missing[:5]}...")
    feature_names = available

# 3. Kiểm tra tích hợp Optuna
print("\n[2] Kiểm tra tích hợp Optuna...")
optuna_file = MODELS_DIR / "best_optuna_params.json"
if optuna_file.exists():
    optuna_params = json.load(open(optuna_file))
    print(f"✓ Đã nạp tham số Optuna:")
    print(f"  XGB: n_est={optuna_params['xgb']['n_estimators']}, lr={optuna_params['xgb']['learning_rate']:.4f}")
    print(f"  LGBM: n_est={optuna_params['lgbm']['n_estimators']}, lr={optuna_params['lgbm']['learning_rate']:.4f}")
else:
    print("✗ Không tìm thấy tham số Optuna")

# 4. Kiểm tra tập test đã được chia chưa
print("\n[3] Kiểm tra các phần dữ liệu đã chia...")
split_dir = BASE_DIR / "scripts" / "data_after_split"
if (split_dir / "test" / "test.csv").exists():
    test_df = pd.read_csv(split_dir / "test" / "test.csv")
    print(f"✓ Tập test tồn tại: {len(test_df):,} dòng")
else:
    print("  Tập test chưa được lưu (sẽ sử dụng phân chia nội bộ)")
    test_df = None

# 5. Nạp model và đánh giá trên test
print("\n[4] Đang nạp model và đánh giá...")
pipeline = joblib.load(model_path)
le = joblib.load(MODELS_DIR / "los_label_encoder.joblib")

# Chuẩn bị dữ liệu test
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.sort_values("date").copy()

split_idx_train = int(len(df) * 0.8)
split_idx_val = int(len(df) * 0.9)

train_df = df.iloc[:split_idx_train].copy()
val_df = df.iloc[split_idx_train:split_idx_val].copy()
test_df = df.iloc[split_idx_val:].copy()

# Lọc các đặc trưng có sẵn
available_features = [f for f in feature_names if f in train_df.columns]

# Mã hóa nhãn mục tiêu
train_df["LOS"] = le.transform(train_df["LOS"])
val_df["LOS"] = le.transform(val_df["LOS"])
test_df["LOS"] = le.transform(test_df["LOS"])

X_train = train_df[available_features]
y_train = train_df["LOS"]
X_val = val_df[available_features]
y_val = val_df["LOS"]
X_test = test_df[available_features]
y_test = test_df["LOS"]

# Đánh giá
y_pred_val = pipeline.predict(X_val)
y_pred_test = pipeline.predict(X_test)

print("\n  === Tập Validation ===")
val_acc = accuracy_score(y_val, y_pred_val)
val_f1 = f1_score(y_val, y_pred_val, average="macro")
print(f"  Độ chính xác: {val_acc:.4f} ({val_acc*100:.2f}%)")
print(f"  Macro F1: {val_f1:.4f}")

print("\n  === Tập Test ===")
test_acc = accuracy_score(y_test, y_pred_test)
test_f1 = f1_score(y_test, y_pred_test, average="macro")
print(f"  Độ chính xác: {test_acc:.4f} ({test_acc*100:.2f}%)")
print(f"  Macro F1: {test_f1:.4f}")

# 6. Phân tích sự dịch chuyển phân phối lớp
print("\n[5] Phân tích sự dịch chuyển phân phối lớp")
print("  Lớp    Train%    Val%    Test%")
print("  " + "-" * 35)
class_names = le.classes_.tolist()
for i, cls in enumerate(class_names):
    train_pct = (y_train == i).mean() * 100
    val_pct = (y_val == i).mean() * 100
    test_pct = (y_test == i).mean() * 100
    shift = abs(val_pct - test_pct)
    flag = "!" if shift > 10 else ""
    print(f"  {cls:<8} {train_pct:6.1f}%   {val_pct:5.1f}%   {test_pct:5.1f}%  {flag}")

# 7. Kiểm tra các đặc trưng rò rỉ mục tiêu đã bị loại trừ
print("\n[6] Kiểm tra loại trừ đặc trưng rò rỉ mục tiêu...")
leakage_features = ["congestion_level_enc", "seg_period_los_mode", "seg_weekday_los_mode", "period_los_mode"]
excluded_count = sum(1 for f in leakage_features if f in feature_names)
print(f"  Đặc trưng rò rỉ trong model: {excluded_count} (nên là 0)")

print("\n" + "=" * 60)
print("  KIỂM TRA HOÀN TẤT")
print("=" * 60)
print(f"\n  Tóm tắt:")
print(f"    Độ chính xác Validation: {val_acc:.4f}")
print(f"    Macro F1 Validation:     {val_f1:.4f}")
print(f"    Độ chính xác Test:        {test_acc:.4f}")
print(f"    Macro F1 Test:            {test_f1:.4f}")
print(f"    Chênh lệch Độ chính xác:  {(val_acc - test_acc)*100:+.2f}%")
print()
