"""
prediction_ITS.py — Giao diện Suy luận (Inference) cho bài toán Traffic LOS

Tính năng:
  - Tự động hóa qua CLI Args (hỗ trợ cronjob).
  - Tự động đối chiếu (Auto-align) features đầu vào so với schema huấn luyện,
    điền NaN cho các cột thiếu để tránh crash.
  - Dự đoán nhãn (LOS) kèm độ tin cậy (Confidence Score).
  - Trả về xác suất chi tiết (Predict Proba) cho từng nhãn (A, B, C, D, E, F) để hỗ trợ ITS.
  - Tối ưu I/O: Lưu metadata định danh + kết quả (thay vì toàn bộ input).
"""

import os
import sys
import json
import time
import argparse
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import joblib

warnings.filterwarnings("ignore")

# ==============================================================================
# LOGGER
# ==============================================================================

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# ==============================================================================
# HÀM PHỤ TRỢ (HELPER FUNCTIONS)
# ==============================================================================

def parse_arguments():
    parser = argparse.ArgumentParser(description="ITS Traffic LOS Inference")

    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    parser.add_argument('--input', type=str, default=str(BASE_DIR / 'scripts' / 'data_after_split' / 'test' / 'test.csv'),
                        help='Đường dẫn tới file CSV cần dự đoán')
    parser.add_argument('--output', type=str, default=str(BASE_DIR / 'scripts' / 'outputs' / 'prediction_result.csv'),
                        help='Đường dẫn file CSV để lưu kết quả dự đoán')
    parser.add_argument('--model_dir', type=str, default=str(BASE_DIR / 'models'),
                        help='Thư mục chứa model và các artifact liên quan')
    
    return parser.parse_args()

def auto_align_features(df: pd.DataFrame, expected_features: list) -> pd.DataFrame:
    """
    So khớp dữ liệu đầu vào với feature schema lúc train.
    - Thiếu cột: Tạo cột mới với giá trị NaN.
    - Dư cột: Loại bỏ.
    - Sắp xếp cột đúng thứ tự lúc train.
    """
    actual_features = set(df.columns)
    expected_set = set(expected_features)
    
    missing_cols = expected_set - actual_features
    extra_cols = actual_features - expected_set
    
    if missing_cols:
        log(f"  [CẢNH BÁO] File input thiếu {len(missing_cols)} cột (đã tự động điền NaN):")
        for col in list(missing_cols)[:5]:
            log(f"    - {col}")
        if len(missing_cols) > 5:
            log(f"    ... và {len(missing_cols) - 5} cột khác")
        
        # Tạo DataFrame rỗng với các cột còn thiếu và ghép vào (nhanh hơn là gán df[col] = np.nan liên tục)
        missing_df = pd.DataFrame(np.nan, index=df.index, columns=list(missing_cols))
        df = pd.concat([df, missing_df], axis=1)

    if extra_cols:
        log(f"  [THÔNG TIN] Bỏ qua {len(extra_cols)} cột thừa trong input so với model.")
    
    # Trả về DataFrame chứa đúng các cột với thứ tự chuẩn
    return df[expected_features]

# ==============================================================================
# MAIN INFERENCE PIPELINE
# ==============================================================================

def main():
    start_time = time.time()
    
    log("=" * 65)
    log("  HỆ THỐNG DỰ ĐOÁN MỨC ĐỘ PHỤC VỤ (LOS) GIAO THÔNG")
    log("=" * 65)
    
    args = parse_arguments()
    input_path = Path(args.input)
    output_path = Path(args.output)
    model_dir = Path(args.model_dir)
    
    # Các file bắt buộc
    model_path = model_dir / 'stacking_ensemble_ITS.joblib'
    le_path = model_dir / 'los_label_encoder.joblib'
    feature_names_path = model_dir / 'feature_names_used.json'
    
    # 1. Kiểm tra tồn tại file đầu vào
    if not input_path.exists():
        log(f"[LỖI] Không tìm thấy file dữ liệu đầu vào: {input_path}")
        sys.exit(1)
        
    for p in [model_path, le_path, feature_names_path]:
        if not p.exists():
            log(f"[LỖI] Bị thiếu Model Artifact: {p}")
            log("Hãy chắc chắn bạn đã chạy train_stacking.py trước!")
            sys.exit(1)

    # P0-1 FIX: Kiểm tra feature_names_used.json cho các feature lỗi/thừa
    KNOWN_BAD_FEATURES = {"s_node_degree"}  # Thực sự lỗi; *_x/*_y là các feature tương tác hợp lệ
    with open(feature_names_path, "r", encoding="utf-8") as f:
        feat_meta = json.load(f)
    bad = [fn for fn in feat_meta.get("feature_names", []) if fn in KNOWN_BAD_FEATURES]
    if bad:
        log(f"[LỖI] feature_names_used.json chứa các feature lỗi: {bad}")
        log("  → Model đã được train với code LỖI (trước khi sửa).")
        log("  → Cần huấn luyện lại model sau khi chạy lại pipeline.")
        sys.exit(1)
            
    # 2. Nạp Models & Metadata
    log("[1/4] Dang nap Model, Metadata va Label Encoder...")
    with open(feature_names_path, "r", encoding="utf-8") as f:
        feat_meta = json.load(f)
    expected_features = feat_meta["feature_names"]
    try:
        pipeline = joblib.load(model_path)
        le = joblib.load(le_path)
        log(f"  ✓ Model da nap (Yeu cau {len(expected_features)} dac trung dau vao).")
    except Exception as e:
        log(f"[LỖI] Quá trình nạp mô hình thất bại: {e}")
        sys.exit(1)
        
    # 3. Đọc dữ liệu & Căn chỉnh Schema
    log(f"\n[2/4] Đọc file đầu vào: {input_path.name}...")
    try:
        df_raw = pd.read_csv(input_path, low_memory=False)
        log(f"  ✓ Tìm thấy {len(df_raw):,} bản ghi.")
    except Exception as e:
        log(f"[LỖI] Lỗi đọc file CSV: {e}")
        sys.exit(1)
        
    log("  Đang so khớp (Auto-align) cấu trúc features...")
    X_test = auto_align_features(df_raw, expected_features)
    
    # 4. Dự đoán (Predict & Predict Proba)
    log(f"\n[3/4] Đang dự đoán mức độ ùn tắc (LOS)...")
    try:
        t0_pred = time.time()

        # Dự đoán nhãn
        y_pred_numeric = pipeline.predict(X_test)
        y_pred_label = le.inverse_transform(y_pred_numeric)

        # Dự đoán xác suất
        y_proba = pipeline.predict_proba(X_test)
        confidence_scores = np.max(y_proba, axis=1)

        # Gán vào bản gốc
        df_raw['LOS_pred'] = y_pred_label
        df_raw['confidence_score'] = np.round(confidence_scores, 4)

        # Khai triển xác suất từng nhãn
        class_names = le.classes_
        for idx, cls_name in enumerate(class_names):
            df_raw[f'prob_LOS_{cls_name}'] = np.round(y_proba[:, idx], 4)

        log(f"  ✓ Suy luận hoàn tất trong {time.time() - t0_pred:.2f}s.")

        # Post-processing: làm mượt nhãn theo thời gian/không gian, hysteresis,
        # debounce flip ngắn, fallback nhãn theo period/segment khi confidence
        # thấp. Mục tiêu: giảm sai số MAE (số bậc LOS lệch) mà không train lại.
        log("  Đang áp dụng post-processing (smoothing + hysteresis + fallback)...")
        try:
            try:
                from scripts.prediction.postprocess import improve_los_predictions
            except Exception:
                # Fallback khi sys.path không chứa project root
                import importlib
                import sys as _sys
                _root = str(Path(__file__).resolve().parent.parent.parent)
                if _root not in _sys.path:
                    _sys.path.insert(0, _root)
                postproc_mod = importlib.import_module("scripts.prediction.postprocess")
                improve_los_predictions = postproc_mod.improve_los_predictions
            df_raw = improve_los_predictions(
                df_raw,
                segment_col='segment_id' if 'segment_id' in df_raw.columns else 'street_name',
                period_col='period' if 'period' in df_raw.columns else None,
            )
            log("  ✓ Post-processing hoàn tất.")
        except Exception as pe:
            log(f"  [CẢNH BÁO] Post-processing bị bỏ qua: {pe}")
    except Exception as e:
        log(f"[LỖI] Quá trình dự đoán gặp lỗi: {e}")
        sys.exit(1)
        
    # 5. Lưu Output (Tối ưu I/O)
    log(f"\n[4/4] Lưu kết quả...")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Chi cần các cột cần thiết: metadata + kết quả dự đoán
        # Bao gồm tất cả các metadata có sẵn trong df_raw (không chỉ 6 cột cố định)
        metadata_cols = ['_id', 'segment_id', 'date', 'period',
                         'street_name', 'long_snode', 'lat_snode', 'long_enode', 'lat_enode',
                         'length', 'max_velocity', 'street_level']
        keep_meta = [c for c in metadata_cols if c in df_raw.columns]

        pred_cols = ['LOS_pred', 'confidence_score'] + [f'prob_LOS_{c}' for c in class_names]

        # Bao gồm tất cả các cột có sẵn ngoài các cột prediction
        other_cols = ['LOS', 'period_hour', 'period_minute', 'is_holiday',
                      'is_weekend', 'is_rush_hour', 'is_night', 'is_working_hours',
                      'is_lunch', 'is_morning_rush', 'is_evening_rush',
                      'time_of_day_cat', 'season', 'vc_ratio',
                      'hist_vel_mean', 'hist_vel_last', 'node_degree']
        keep_other = [c for c in other_cols if c in df_raw.columns]

        # Xuất các cột cần thiết
        df_output = df_raw[keep_meta + keep_other + pred_cols]

        df_output.to_csv(output_path, index=False)
        
        file_size = output_path.stat().st_size / 1_048_576
        log(f"  ✓ Đã lưu file: {output_path.name} ({file_size:.2f} MB)")
    except Exception as e:
        log(f"[LỖI] Lỗi khi ghi file output: {e}")
        sys.exit(1)
        
    total_time = time.time() - start_time
    log(f"\n{'=' * 65}")
    log(f"HOÀN TẤT: Đã dự đoán {len(df_raw):,} mẫu trong {total_time:.2f}s.")
    log(f"{'=' * 65}")

if __name__ == '__main__':
    main()
