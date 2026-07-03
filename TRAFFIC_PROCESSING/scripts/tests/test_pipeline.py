"""
Unit tests cho pipeline Traffic LOS của ITS.

Chạy với:
    pytest scripts/tests/ -v
    pytest scripts/tests/ -v --cov=scripts --cov-report=html
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

# Thêm thư mục scripts vào path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.data_processing.preprocessing import (
    assign_los_from_velocity,
    detect_velocity_outliers,
)
from scripts.feature_engineering.feature_engineering import (
    extract_temporal_features,
    compute_geometry_features,
    compute_traffic_features,
    compute_infrastructure_features,
    create_interaction_features,
)


class TestLOSLabeling:
    """Kiểm tra chức năng gán nhãn LOS."""

    def test_los_hcm_strict_boundaries(self):
        """Kiểm tra ngưỡng LOS nghiêm ngặt của HCM."""
        df = pd.DataFrame({
            "velocity": [10, 25, 35, 50, 65, 80],
            "max_velocity": [100, 100, 100, 100, 100, 100],
        })
        result = assign_los_from_velocity(df, method="hcm_strict")
        los = result["LOS_assigned"].tolist()
        # Tỷ lệ V/C: 0.10->A, 0.25->B, 0.35->B, 0.50->C, 0.65->D, 0.80->E
        assert los[0] == "A"
        assert los[1] == "B"
        assert los[2] == "B"
        assert los[3] == "C"
        assert los[4] == "D"
        assert los[5] == "E"

    def test_los_edge_cases(self):
        """Kiểm tra LOS cho các trường hợp biên."""
        df = pd.DataFrame({
            "velocity": [0, 100, 200],
            "max_velocity": [100, 100, 100],
        })
        result = assign_los_from_velocity(df, method="hcm_strict")
        los = result["LOS_assigned"].tolist()
        assert los[0] == "A"  # V/C = 0
        assert los[1] == "F"  # V/C = 1.0
        assert los[2] == "F"   # V/C = 2.0 (cắt về 5)


class TestOutlierDetection:
    """Kiểm tra phát hiện ngoại lai."""

    def test_velocity_outliers_iqr(self):
        """Kiểm tra phát hiện ngoại lai dựa trên IQR."""
        df = pd.DataFrame({
            "velocity": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 1000],
        })
        result = detect_velocity_outliers(df, methods=["iqr"])
        assert "is_outlier" in result.columns
        assert result["is_outlier"].iloc[-1] == True  # 1000 nên là ngoại lai

    def test_velocity_outliers_zscore(self):
        """Kiểm tra phát hiện ngoại lai bằng z-score."""
        np.random.seed(42)
        velocities = np.random.normal(50, 10, 100)
        velocities = np.concatenate([velocities, [200, 250, 300]])
        df = pd.DataFrame({"velocity": velocities})
        result = detect_velocity_outliers(df, methods=["zscore"])
        assert "is_outlier" in result.columns


class TestTemporalFeatures:
    """Kiểm tra trích xuất đặc trưng thời gian."""

    def test_extract_temporal_features(self):
        """Kiểm tra trích xuất đặc trưng thời gian cơ bản."""
        df = pd.DataFrame({
            "period": ["period_8_0", "period_12_30", "period_18_0"],
            "date": ["2024-01-15", "2024-01-16", "2024-01-20"],  # Thứ 2, Thứ 3, Thứ 7
        })
        result = extract_temporal_features(df)
        assert "period_hour" in result.columns
        assert "is_weekend" in result.columns
        assert "is_morning_rush" in result.columns
        assert result["is_weekend"].iloc[2] == 1  # Thứ 7

    def test_rush_hour_flags(self):
        """Kiểm tra phát hiện giờ cao điểm."""
        df = pd.DataFrame({
            "period": ["period_7_0", "period_8_0", "period_17_30", "period_20_0"],
            "date": ["2024-01-15"] * 4,
        })
        result = extract_temporal_features(df)
        assert result["is_morning_rush"].iloc[0] == 1
        assert result["is_morning_rush"].iloc[1] == 1
        assert result["is_evening_rush"].iloc[2] == 1
        assert result["is_rush_hour"].sum() == 3


class TestGeometryFeatures:
    """Kiểm tra tính toán đặc trưng hình học."""

    def test_haversine_distance(self):
        """Kiểm tra tính khoảng cách Haversine."""
        df = pd.DataFrame({
            "long_snode": [106.7],
            "lat_snode": [10.8],
            "long_enode": [106.72],
            "lat_enode": [10.82],
        })
        result = compute_geometry_features(df)
        assert "length_haversine_km" in result.columns
        assert result["length_haversine_km"].iloc[0] > 0
        assert result["length_haversine_km"].iloc[0] < 10  # Nên nhỏ

    def test_bearing_calculation(self):
        """Kiểm tra góc phương vị đoạn đường."""
        df = pd.DataFrame({
            "long_snode": [106.7],
            "lat_snode": [10.8],
            "long_enode": [106.72],
            "lat_enode": [10.82],
        })
        result = compute_geometry_features(df)
        assert "segment_bearing_deg" in result.columns


class TestTrafficFeatures:
    """Kiểm tra tính toán đặc trưng giao thông."""

    def test_vc_ratio_calculation(self):
        """Kiểm tra tính tỷ lệ V/C."""
        df = pd.DataFrame({
            "velocity": [50, 75, 30],
            "length": [1000, 1000, 1000],
            "max_velocity": [100, 100, 100],
        })
        result = compute_traffic_features(df)
        assert "vc_ratio" in result.columns
        np.testing.assert_almost_equal(result["vc_ratio"].iloc[0], 0.5)
        np.testing.assert_almost_equal(result["vc_ratio"].iloc[1], 0.75)

    def test_travel_time_calculation(self):
        """Kiểm tra các đặc trưng thời gian di chuyển."""
        df = pd.DataFrame({
            "velocity": [50, 0],  # 0 để kiểm tra xử lý an toàn
            "length": [5000, 5000],  # mét
            "max_velocity": [100, 100],
        })
        result = compute_traffic_features(df)
        assert "travel_time_actual" in result.columns
        assert "travel_time_free_flow" in result.columns
        assert result["travel_time_actual"].notna().all()


class TestInfrastructureFeatures:
    """Kiểm tra tính toán đặc trưng cơ sở hạ tầng."""

    def test_street_priority_mapping(self):
        """Kiểm tra ánh xạ ưu tiên đường."""
        df = pd.DataFrame({
            "street_type": ["trunk", "primary", "residential"],
            "length": [1000, 1000, 1000],
            "max_velocity": [80, 60, 30],
        })
        result = compute_infrastructure_features(df)
        assert "street_priority" in result.columns
        assert result["street_priority"].iloc[0] > result["street_priority"].iloc[2]

    def test_capacity_proxy(self):
        """Kiểm tra tính toán proxy công suất."""
        df = pd.DataFrame({
            "street_type": ["primary"],
            "length": [1000],
            "max_velocity": [60],
        })
        result = compute_infrastructure_features(df)
        assert "capacity_proxy" in result.columns
        assert result["capacity_proxy"].iloc[0] == 60000


class TestInteractionFeatures:
    """Kiểm tra tạo đặc trưng tương tác."""

    def test_interaction_features_created(self):
        """Kiểm tra đặc trưng tương tác được tạo."""
        df = pd.DataFrame({
            "street_level": [3, 2],
            "length": [1000, 500],
            "vc_ratio": [0.5, 0.8],
            "period_hour": [8, 18],
            "weekday": [1, 1],
            "is_rush_hour": [1, 1],
            "street_priority": [3, 4],
            "est_lane_count": [2, 3],
            "length_haversine_km": [1.0, 0.5],
        })
        result = create_interaction_features(df)
        assert "level_x_length" in result.columns
        assert "vc_x_hour" in result.columns


class TestDataIntegrity:
    """Kiểm tra tính toàn vẹn dữ liệu."""

    def test_no_infinity_values(self):
        """Kiểm tra các đặc trưng không tạo ra giá trị vô cực."""
        df = pd.DataFrame({
            "velocity": [50, 75, 30],
            "length": [1000, 1000, 1000],
            "max_velocity": [100, 100, 100],
        })
        result = compute_traffic_features(df)
        for col in result.columns:
            if result[col].dtype in [np.float64, np.float32]:
                assert not np.isinf(result[col]).any(), f"Vô cực trong cột {col}"

    def test_no_negative_vc_ratio(self):
        """Kiểm tra tỷ lệ V/C không âm."""
        df = pd.DataFrame({
            "velocity": [-10, 0, 50],
            "length": [1000, 1000, 1000],
            "max_velocity": [100, 100, 100],
        })
        result = compute_traffic_features(df)
        assert (result["vc_ratio"] >= 0).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
