"""
postprocess.py — Post-processing cho LOS predictions.

Mục tiêu: giảm sai số MAE (số bậc LOS lệch) và ổn định nhãn theo thời gian/không
gian mà KHÔNG cần train lại model. Các bước (theo thứ tự):

  1. ``smooth_probabilities`` — làm mượt vector xác suất bằng trung bình trượt
     theo thời gian (cùng segment) hoặc theo segment (cùng period). Mỗi mẫu đầu
     vào chỉ được dùng làm tín hiệu, đầu ra là vector đã làm mượt.
  2. ``debounce_short_flips`` — nếu nhãn LOS đổi chỉ trong 1 mẫu rồi quay lại
     nhãn trước đó, ép về nhãn trước.
  3. ``hysteresis`` — khi nhãn mới ở biên confidence thấp, chỉ chấp nhận nếu
     xác suất nhãn mới vượt ngưỡng ``switch_in``; nếu không thì giữ nhãn cũ
     với ngưỡng ``stay`` thấp hơn.
  4. ``neighbor_fallback`` — với các mẫu confidence rất thấp và không có láng
     giềng đáng tin, fallback về nhãn phổ biến nhất trong cùng segment/period.

Mọi hàm đều nhận ``pd.DataFrame`` đã có cột ``LOS_pred``, ``confidence_score``
và các cột xác suất ``prob_LOS_{A..F}``. Trả về DataFrame mới (không mutate đầu
vào) với cùng schema, các giá trị đã hiệu chỉnh.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


LOS_ORDER = ["A", "B", "C", "D", "E", "F"]
LOS_INDEX = {los: i for i, los in enumerate(LOS_ORDER)}


def _required_columns(df: pd.DataFrame) -> None:
    missing = [c for c in ("LOS_pred", "confidence_score") if c not in df.columns]
    if missing:
        raise ValueError(
            f"DataFrame thiếu các cột bắt buộc cho post-processing: {missing}"
        )
    prob_cols = [f"prob_LOS_{los}" for los in LOS_ORDER]
    miss_prob = [c for c in prob_cols if c not in df.columns]
    if miss_prob:
        raise ValueError(
            f"DataFrame thiếu các cột xác suất LOS: {miss_prob}. "
            "Hãy chắc chắn prediction_ITS.py đã ghi đủ prob_LOS_*."
        )


def _proba_matrix(df: pd.DataFrame) -> np.ndarray:
    cols = [f"prob_LOS_{los}" for los in LOS_ORDER]
    return df[cols].to_numpy(dtype=float)


def _label_from_proba(p: np.ndarray) -> np.ndarray:
    return np.array(LOS_ORDER)[np.argmax(p, axis=1)]


def _label_to_index(labels: Iterable[str]) -> np.ndarray:
    out = np.empty(len(list(labels)), dtype=int) if not isinstance(labels, np.ndarray) else np.empty(labels.shape[0], dtype=int)
    arr = np.asarray(labels, dtype=object)
    for i, lab in enumerate(arr):
        out[i] = LOS_INDEX.get(lab, 0)
    return out


# ----------------------------------------------------------------------------- #
# 1. Smooth probability vectors
# ----------------------------------------------------------------------------- #

def smooth_probabilities(
    df: pd.DataFrame,
    by: str = "segment_id",
    window: int = 3,
) -> pd.DataFrame:
    """Làm mượt vector xác suất LOS theo nhóm ``by`` với cửa sổ trượt.

    Các mẫu không có ``by`` (NaN/None) được giữ nguyên.
    """
    _required_columns(df)
    if df.empty or window <= 1 or by not in df.columns:
        return df.copy()

    out = df.copy()
    p = _proba_matrix(out)
    grouped = out.groupby(by, sort=False, dropna=False).indices
    for _, idx in grouped.items():
        idx = np.asarray(idx)
        if len(idx) < 2:
            continue
        seg = p[idx]
        # Centered rolling mean with edge reflection so length is preserved
        kernel = np.ones(window, dtype=float) / window
        smoothed = np.apply_along_axis(
            lambda row: np.convolve(row, kernel, mode="same"), axis=0, arr=seg
        )
        # Re-normalize so each row still sums to 1
        smoothed = np.clip(smoothed, 1e-9, None)
        smoothed = smoothed / smoothed.sum(axis=1, keepdims=True)
        p[idx] = smoothed

    for j, los in enumerate(LOS_ORDER):
        out[f"prob_LOS_{los}"] = np.round(p[:, j], 4)
    out["confidence_score"] = np.round(p.max(axis=1), 4)
    out["LOS_pred"] = _label_from_proba(p)
    return out


# ----------------------------------------------------------------------------- #
# 2. Debounce single-sample flips
# ----------------------------------------------------------------------------- #

def debounce_short_flips(
    df: pd.DataFrame,
    by: str = "segment_id",
    max_flip_len: int = 1,
) -> pd.DataFrame:
    """Bỏ qua các lật nhãn ngắn hơn hoặc bằng ``max_flip_len`` mẫu trong cùng nhóm."""
    _required_columns(df)
    if df.empty or by not in df.columns or max_flip_len < 1:
        return df.copy()

    out = df.copy()
    for _, idx in out.groupby(by, sort=False, dropna=False).indices.items():
        idx = np.asarray(idx)
        if len(idx) <= max_flip_len + 1:
            continue
        labels = out["LOS_pred"].to_numpy()[idx]
        cleaned = labels.copy()
        i = 0
        n = len(labels)
        while i < n:
            # find run length of labels[i]
            j = i
            while j + 1 < n and labels[j + 1] == labels[i]:
                j += 1
            run_len = j - i + 1
            if run_len <= max_flip_len and i > 0 and (j + 1) < n:
                prev = labels[i - 1]
                nxt = labels[j + 1]
                if prev == nxt and prev != labels[i]:
                    cleaned[i:j + 1] = prev
            i = j + 1
        out.iloc[idx, out.columns.get_loc("LOS_pred")] = cleaned
    return out


# ----------------------------------------------------------------------------- #
# 3. Hysteresis
# ----------------------------------------------------------------------------- #

def hysteresis(
    df: pd.DataFrame,
    by: str = "segment_id",
    switch_in: float = 0.55,
    stay: float = 0.35,
) -> pd.DataFrame:
    """Hysteresis: giữ nhãn cũ trừ khi nhãn mới đủ mạnh.

    Với mỗi nhóm theo ``by``, nhãn mới ở mẫu ``i`` chỉ được chấp nhận nếu
    xác suất của nó ``>= switch_in``. Nếu giữa hai nhãn liên tiếp mà xác suất
    nhãn hiện tại còn cao hơn ``stay``, tiếp tục giữ nhãn cũ.
    """
    _required_columns(df)
    if df.empty or by not in df.columns:
        return df.copy()

    out = df.copy()
    p = _proba_matrix(out)
    for _, idx in out.groupby(by, sort=False, dropna=False).indices.items():
        idx = np.asarray(idx)
        if len(idx) < 2:
            continue
        labels = out["LOS_pred"].to_numpy()[idx].copy()
        probs = p[idx]
        current = labels[0]
        for k in range(1, len(labels)):
            new_lab = labels[k]
            if new_lab == current:
                continue
            new_p = probs[k, LOS_INDEX[new_lab]]
            cur_p = probs[k, LOS_INDEX[current]]
            # Accept switch only if new label probability clears the high bar
            if new_p >= switch_in and new_p > cur_p:
                current = new_lab
            # Otherwise keep previous label (hysteresis)
            labels[k] = current
        out.iloc[idx, out.columns.get_loc("LOS_pred")] = labels
    return out


# ----------------------------------------------------------------------------- #
# 4. Confidence-weighted neighbor fallback
# ----------------------------------------------------------------------------- #

def neighbor_fallback(
    df: pd.DataFrame,
    by_period: str = "period",
    by_segment: str = "segment_id",
    low_conf_threshold: float = 0.4,
) -> pd.DataFrame:
    """Với các mẫu confidence thấp, fallback về nhãn phổ biến nhất trong cùng
    period (cùng ``by_period``). Nếu không có, dùng cùng ``by_segment``.

    Chỉ áp dụng khi confidence < ``low_conf_threshold``. Trả về cùng schema.
    """
    _required_columns(df)
    if df.empty:
        return df.copy()

    out = df.copy()
    low_mask = out["confidence_score"] < low_conf_threshold
    if not low_mask.any():
        return out

    # Build majority label per period
    if by_period in out.columns:
        per_period = (
            out.loc[~low_mask]
            .groupby(by_period)["LOS_pred"]
            .agg(lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0])
        )
    else:
        per_period = pd.Series(dtype=object)

    # Fallback: majority per segment
    if by_segment in out.columns:
        per_segment = (
            out.loc[~low_mask]
            .groupby(by_segment)["LOS_pred"]
            .agg(lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0])
        )
    else:
        per_segment = pd.Series(dtype=object)

    fallback = out["LOS_pred"].copy()
    if not per_period.empty:
        for k in out.index[low_mask]:
            if k in per_period.index:
                fallback.loc[k] = per_period.loc[k]
    if not per_segment.empty:
        for k in out.index[low_mask]:
            if k in per_segment.index:
                fallback.loc[k] = per_segment.loc[k]
    # If still missing, keep original
    fallback = fallback.where(fallback.notna(), out["LOS_pred"])
    out.loc[low_mask, "LOS_pred"] = fallback.loc[low_mask].values
    return out


# ----------------------------------------------------------------------------- #
# Convenience: full pipeline
# ----------------------------------------------------------------------------- #

def improve_los_predictions(
    df: pd.DataFrame,
    segment_col: str = "segment_id",
    period_col: str = "period",
    smooth_window: int = 3,
    switch_in: float = 0.55,
    stay: float = 0.35,
    low_conf: float = 0.4,
) -> pd.DataFrame:
    """Chạy toàn bộ pipeline post-processing theo thứ tự an toàn:

    1. Làm mượt xác suất theo segment (giảm nhiễu).
    2. Debounce các lật nhãn 1-frame.
    3. Hysteresis trên chuỗi nhãn segment.
    4. Fallback nhãn theo period/segment cho mẫu confidence thấp.
    """
    out = df.copy()
    out = smooth_probabilities(out, by=segment_col, window=smooth_window)
    out = debounce_short_flips(out, by=segment_col, max_flip_len=1)
    out = hysteresis(out, by=segment_col, switch_in=switch_in, stay=stay)
    out = neighbor_fallback(
        out,
        by_period=period_col,
        by_segment=segment_col,
        low_conf_threshold=low_conf,
    )
    return out
