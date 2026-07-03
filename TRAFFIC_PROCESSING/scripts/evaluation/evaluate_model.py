"""
evaluate_model.py — Đánh giá chuyên sâu và trực quan hóa mô hình Stacking Ensemble
"""
import os
import json
import sys
import warnings
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    average_precision_score,
    f1_score,
)
from sklearn.preprocessing import label_binarize
from sklearn.calibration import CalibratedClassifierCV

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).parent.parent.parent
OUTPUTS_DIR = BASE_DIR / "scripts" / "outputs"
MODELS_DIR = BASE_DIR / "models"
EVAL_DIR = BASE_DIR / "evaluation_results"
EVAL_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# HIỆU CHỈNH (CALIBRATION)
# ==============================================================================

def calibrate_pipeline(pipeline, X_calib, y_calib, le):
    """Hiệu chỉnh pipeline stacking bằng hồi quy đẳng thức (isotonic regression)."""
    print("  Đang hiệu chỉnh xác suất pipeline (isotonic)...")
    calibrated = CalibratedClassifierCV(pipeline, method="isotonic", cv=3)
    calibrated.fit(X_calib, y_calib)
    print("  Hiệu chỉnh hoàn tất.")
    return calibrated


def optimize_thresholds_per_class(y_true, y_probs, classes):
    """
    Tối ưu ngưỡng cho từng lớp để tối đa hóa macro F1 bằng coordinate descent.
    Với mỗi lớp, tìm ngưỡng xác suất tối đa hóa F1 khi
    các mẫu có P(lớp) >= ngưỡng được dự đoán là lớp đó.
    """
    print("  Đang tối ưu ngưỡng cho từng lớp cho macro F1...")
    n_classes = len(classes)
    best_thresholds = np.ones(n_classes) * 0.5

    for epoch in range(50):
        improved = False
        for c_idx in range(n_classes):
            best_f1 = 0
            best_t = best_thresholds[c_idx]

            for t in np.arange(0.05, 0.95, 0.05):
                thresholds = best_thresholds.copy()
                thresholds[c_idx] = t

                y_pred_opt = np.argmax(y_probs * thresholds, axis=1)
                f1_scores = []
                for i in range(n_classes):
                    mask = y_true == i
                    if mask.sum() == 0:
                        f1_scores.append(0)
                        continue
                    tp = ((y_pred_opt == i) & mask).sum()
                    fp = ((y_pred_opt == i) & ~mask).sum()
                    fn = ((y_true == i) & (y_pred_opt != i)).sum()
                    p = tp / (tp + fp + 1e-10)
                    r = tp / (tp + fn + 1e-10)
                    f1_scores.append(2 * p * r / (p + r + 1e-10))

                macro_f1 = np.mean(f1_scores)
                if macro_f1 > best_f1:
                    best_f1 = macro_f1
                    best_t = t

            if abs(best_t - best_thresholds[c_idx]) > 0.01:
                best_thresholds[c_idx] = best_t
                improved = True

        if not improved:
            break

    y_pred_optimized = np.argmax(y_probs * best_thresholds, axis=1)

    # Đánh giá
    opt_f1 = f1_score(y_true, y_pred_optimized, average="macro")
    base_f1 = f1_score(y_true, np.argmax(y_probs, axis=1), average="macro")
    print(f"    Macro F1 cơ bản: {base_f1:.4f}  |  Macro F1 sau tối ưu: {opt_f1:.4f}  (+{(opt_f1 - base_f1)*100:+.2f}%)")
    print(f"    Ngưỡng cho từng lớp: {dict(zip(classes, [f'{t:.2f}' for t in best_thresholds]))}")

    return best_thresholds, opt_f1, base_f1

def plot_confusion_matrix(y_true, y_pred, classes):
    class_ids = np.arange(len(classes))
    cm = confusion_matrix(y_true, y_pred, labels=class_ids)
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=classes, yticklabels=classes)
    plt.title("Ma trận nhầm lẫn - Mức độ phục vụ giao thông (LOS)")
    plt.xlabel("LOS Dự đoán")
    plt.ylabel("LOS Thực tế")
    plt.tight_layout()
    plt.savefig(EVAL_DIR / "confusion_matrix.png", dpi=300)
    plt.close()
    print("  Đã lưu: confusion_matrix.png")

def plot_precision_recall_curves(y_true, y_probs, classes):
    class_ids = np.arange(len(classes))
    y_true_bin = label_binarize(y_true, classes=class_ids)
    plt.figure(figsize=(10, 8))
    
    colors = ['blue', 'green', 'red', 'cyan', 'magenta', 'orange']
    for i in range(len(classes)):
        if i >= y_true_bin.shape[1]: break
        precision, recall, _ = precision_recall_curve(y_true_bin[:, i], y_probs[:, i])
        ap = average_precision_score(y_true_bin[:, i], y_probs[:, i])
        plt.plot(recall, precision, color=colors[i%len(colors)], lw=2,
                 label=f'LOS {classes[i]} (AP = {ap:.2f})')
                 
    plt.xlabel("Recall (Độ phủ)")
    plt.ylabel("Precision (Độ chính xác)")
    plt.title("Đường cong Precision-Recall theo từng Lớp")
    plt.legend(loc="best")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(EVAL_DIR / "precision_recall_curves.png", dpi=300)
    plt.close()
    print("  Đã lưu: precision_recall_curves.png")

def plot_feature_importance():
    imp_path = MODELS_DIR / "feature_importance_mean.csv"
    if not imp_path.exists():
        print("  [CẢNH BÁO] Không tìm thấy feature_importance_mean.csv")
        return

    df = pd.read_csv(imp_path).head(20) # Top 20
    plt.figure(figsize=(12, 8))
    sns.barplot(x="importance", y="feature", data=df, palette="viridis")
    plt.title("Top 20 Đặc trưng Quan trọng nhất quyết định Tắc nghẽn (XAI)")
    plt.xlabel("Độ quan trọng trung bình (Mô hình Base)")
    plt.ylabel("Đặc trưng")
    plt.tight_layout()
    plt.savefig(EVAL_DIR / "feature_importance.png", dpi=300)
    plt.close()
    print("  Đã lưu: feature_importance.png")


def encode_los_for_evaluation(los_series, le):
    """Chuẩn hóa nhãn LOS từ split test về id số 0..n_classes-1.

    train_stacking.py lưu train/val/test sau khi LabelEncoder đã encode LOS,
    nên file test.csv hiện tại thường chứa 0..5. Hàm này vẫn hỗ trợ trường hợp
    test.csv chứa nhãn gốc A..F để script không phụ thuộc vào một định dạng duy nhất.
    """
    raw = los_series.copy()
    class_ids = np.arange(len(le.classes_))

    numeric = pd.to_numeric(raw, errors="coerce")
    numeric_int = numeric.fillna(-999999).round().astype(int)
    numeric_valid = (
        numeric.notna()
        & np.isclose(numeric, numeric.round())
        & numeric_int.isin(class_ids)
    )
    if numeric_valid.all():
        return numeric_int.to_numpy(), numeric_valid.to_numpy()

    string_values = raw.astype(str)
    valid_string = string_values.isin([str(c) for c in le.classes_])
    encoded = np.full(len(raw), -1, dtype=int)
    if valid_string.any():
        encoded[valid_string.to_numpy()] = le.transform(string_values[valid_string])
    return encoded, valid_string.to_numpy()


# ==============================================================================
# PHÂN TÍCH SHAP
# ==============================================================================

def run_shap_analysis(pipeline, X_sample, feature_names, classes, n_samples=500):
    """
    Chạy phân tích SHAP trên pipeline stacking.
    Sử dụng các base estimators cho giá trị SHAP vì meta-learner
    hoạt động trên xác suất, không phải đặc trưng thô.
    """
    try:
        import shap
    except ImportError:
        print("  [THÔNG TIN] SHAP chưa được cài đặt. Chạy: pip install shap")
        return None

    print(f"  Đang chạy phân tích SHAP trên {n_samples} mẫu...")

    # Sử dụng XGBoost làm mô hình base đại diện cho SHAP
    stacking_clf = pipeline.named_steps["stacking"]
    try:
        xgb_model = stacking_clf.named_estimators_["xgb"]
    except Exception:
        print("  [CẢNH BÁO] Không tìm thấy estimator XGBoost trong pipeline")
        return None

    # Lấy mẫu dữ liệu cho SHAP
    if len(X_sample) > n_samples:
        idx = np.random.choice(len(X_sample), n_samples, replace=False)
        X_shap = X_sample.iloc[idx]
    else:
        X_shap = X_sample

    # Sử dụng tập nền nhỏ cho TreeExplainer
    background_size = min(100, len(X_shap))
    background = X_shap.iloc[:background_size]

    try:
        explainer = shap.TreeExplainer(xgb_model, data=background)
        shap_values = explainer.shap_values(X_shap)
    except Exception as e:
        print(f"  [CẢNH BÁO] Tính toán SHAP thất bại: {e}")
        return None

    # SHAP summary theo từng lớp
    mean_abs_shap = {}
    for i, cls_name in enumerate(classes):
        sv = shap_values[i] if isinstance(shap_values, list) else shap_values
        if sv is None:
            continue
        mean_abs = np.abs(sv).mean(axis=0)
        mean_abs_shap[cls_name] = mean_abs

    # Trung bình SHAP qua các lớp
    if isinstance(shap_values, list):
        all_shap = np.stack([sv for sv in shap_values if sv is not None])
        mean_shap = np.abs(all_shap).mean(axis=0)
    else:
        mean_shap = np.abs(shap_values).mean(axis=0)

    # Vẽ: SHAP summary (bar)
    plt.figure(figsize=(12, 10))
    shap_df = pd.DataFrame({
        "feature": feature_names,
        "mean_abs_shap": mean_shap
    }).sort_values("mean_abs_shap", ascending=True).tail(25)

    plt.barh(shap_df["feature"], shap_df["mean_abs_shap"], color="steelblue")
    plt.xlabel("Giá trị |SHAP| trung bình")
    plt.title("Tóm tắt SHAP — Top 25 Đặc trưng (XGBoost)")
    plt.tight_layout()
    plt.savefig(EVAL_DIR / "shap_summary.png", dpi=300)
    plt.close()
    print("  Đã lưu: shap_summary.png")

    # Vẽ: SHAP beeswarm (đặc trưng quan trọng nhất theo từng lớp)
    if isinstance(shap_values, list) and len(shap_values) > 0:
        try:
            plt.figure(figsize=(12, 10))
            shap.summary_plot(
                shap_values[0], X_shap,
                feature_names=feature_names,
                show=False, max_display=20
            )
            plt.title("SHAP Beeswarm — Lớp A so với các lớp khác")
            plt.tight_layout()
            plt.savefig(EVAL_DIR / "shap_beeswarm.png", dpi=300)
            plt.close()
            print("  Đã lưu: shap_beeswarm.png")
        except Exception:
            pass

    # Lưu giá trị SHAP vào CSV
    shap_df_full = pd.DataFrame({
        "feature": feature_names,
        "mean_abs_shap": mean_shap
    }).sort_values("mean_abs_shap", ascending=False)
    shap_df_full.to_csv(EVAL_DIR / "shap_values.csv", index=False)
    print(f"  Đã lưu: shap_values.csv")

    return shap_values

def main():
    print("="*60)
    print("  Đánh giá Mô hình & Trực quan hóa XAI")
    print("="*60)
    
    model_path = MODELS_DIR / "stacking_ensemble_ITS.joblib"
    encoder_path = MODELS_DIR / "los_label_encoder.joblib"
    # P0-2 FIX: Sử dụng data_after_split/test/test.csv nhất quán với train_stacking.py
    test_path = BASE_DIR / "scripts" / "data_after_split" / "test" / "test.csv"
    feature_names_path = MODELS_DIR / "feature_names_used.json"
    
    if not (model_path.exists() and test_path.exists()):
        print("[LỖI] Phải huấn luyện model và có test.csv trước.")
        print(f"  model: {model_path}")
        print(f"  test:  {test_path}")
        return
        
    print("1. Đang tải dữ liệu test và model...")
    pipeline = joblib.load(model_path)
    le = joblib.load(encoder_path)
    test_df = pd.read_csv(test_path)
    
    with open(feature_names_path, "r") as f:
        feature_names = json.load(f)["feature_names"]
        
    # P0-2 FIX: Căn chỉnh đặc trưng test để khớp với schema huấn luyện.
    # Giữ test_df gốc để không làm mất cột nhãn LOS và các cột audit.
    X_all = test_df.copy()
    missing_feats = set(feature_names) - set(X_all.columns)
    extra_feats = set(X_all.columns) - set(feature_names)
    if missing_feats:
        print(f"  [CẢNH BÁO] Dữ liệu test thiếu {len(missing_feats)} đặc trưng, điền NaN")
        for col in list(missing_feats)[:5]:
            print(f"    - {col}")
        missing_df = pd.DataFrame(np.nan, index=X_all.index, columns=list(missing_feats))
        X_all = pd.concat([X_all, missing_df], axis=1)
    if extra_feats:
        print(f"  [THÔNG TIN] Bỏ {len(extra_feats)} cột thừa không có trong đặc trưng model")
    X_all = X_all[feature_names]

    if "LOS" not in test_df.columns:
        print("[LỖI] test.csv không có cột LOS để đánh giá.")
        return

    y_encoded, valid_mask = encode_los_for_evaluation(test_df["LOS"], le)
    test_df_filtered = test_df.loc[valid_mask].reset_index(drop=True)
    if len(test_df_filtered) == 0:
        print("[LỖI] Tất cả các dòng test đã bị lọc — kiểm tra tính nhất quán mã hóa nhãn LOS")
        print(f"  le.classes_ = {le.classes_}")
        print(f"  unique LOS in test = {test_df['LOS'].unique()[:10]}")
        return
    if len(test_df_filtered) < len(test_df):
        print(f"  [CẢNH BÁO] Bỏ {len(test_df) - len(test_df_filtered):,} dòng có nhãn LOS không hợp lệ.")

    X_test = X_all.loc[valid_mask].reset_index(drop=True)
    y_test = y_encoded[valid_mask]
    classes = le.classes_
    
    print(f"2. Đang dự đoán trên tập test ({len(test_df_filtered):,} mẫu, {len(feature_names)} đặc trưng)...")
    y_pred = pipeline.predict(X_test)
    try:
        y_probs = pipeline.predict_proba(X_test)
    except Exception:
        y_probs = None
        
    print("3. Đang tạo Báo cáo và Trực quan hóa...")
    class_ids = np.arange(len(classes))
    report = classification_report(
        y_test,
        y_pred,
        labels=class_ids,
        target_names=[f"LOS_{c}" for c in classes],
    )
    print("\n--- Báo cáo Phân loại (Tập Test) ---")
    print(report)
    with open(EVAL_DIR / "classification_report.txt", "w") as f:
        f.write(report)

    plot_confusion_matrix(y_test, y_pred, classes)
    if y_probs is not None:
        plot_precision_recall_curves(y_test, y_probs, classes)
    plot_feature_importance()

    # 4. Tối ưu ngưỡng (ngưỡng cho từng lớp cho macro F1)
    if y_probs is not None:
        thresholds, opt_f1, base_f1 = optimize_thresholds_per_class(
            y_test, y_probs, classes
        )
        # Lưu ngưỡng
        thresh_path = EVAL_DIR / "optimized_thresholds.json"
        with open(thresh_path, "w") as f:
            json.dump({
                "thresholds": {str(c): float(t) for c, t in zip(classes, thresholds)},
                "base_macro_f1": float(base_f1),
                "optimized_macro_f1": float(opt_f1),
            }, f, indent=2)
        print(f"  Đã lưu: optimized_thresholds.json")

    # 5. Phân tích SHAP (trên mẫu tập test)
    if y_probs is not None and len(X_test) > 50:
        shap_values = run_shap_analysis(pipeline, X_test, feature_names, classes, n_samples=500)

    print(f"\nTất cả kết quả đánh giá được lưu tại: {EVAL_DIR}")
    
if __name__ == "__main__":
    main()
