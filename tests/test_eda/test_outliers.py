"""Tests for outlier detection.

Convention: 07-Testing §3 — Arrange-Act-Assert.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.eda.stats.outliers import compute_outlier_stats


class TestComputeOutlierStats:
    """Verify IQR and z-score outlier detection."""

    def test_should_detect_iqr_outliers_when_extreme_values(self) -> None:
        values = list(range(100)) + [999]
        df = pd.DataFrame({"x": values})
        result = compute_outlier_stats(df, ["x"], iqr_factor=1.5)
        assert result.iloc[0]["iqr_outlier_count"] >= 1

    def test_should_detect_zscore_outliers_when_extreme_values(self) -> None:
        values = list(range(100)) + [999]
        df = pd.DataFrame({"x": values})
        result = compute_outlier_stats(df, ["x"], zscore_threshold=3.0)
        assert result.iloc[0]["zscore_outlier_count"] >= 1

    def test_should_return_zero_outliers_when_constant(self) -> None:
        df = pd.DataFrame({"x": [5.0] * 100})
        result = compute_outlier_stats(df, ["x"])
        assert result.iloc[0]["iqr_outlier_count"] == 0
        assert result.iloc[0]["zscore_outlier_count"] == 0

    def test_should_return_bounds_when_normal_data(
        self, sample_df: pd.DataFrame, sample_feature_cols: list[str],
    ) -> None:
        result = compute_outlier_stats(sample_df, sample_feature_cols)
        row_a = result[result["feature_name"] == "feat_a"].iloc[0]
        assert row_a["iqr_lower"] is not None
        assert row_a["iqr_upper"] is not None
        assert row_a["iqr_lower"] < row_a["iqr_upper"]

    def test_should_handle_empty_column_after_coerce(self) -> None:
        df = pd.DataFrame({"x": [np.nan, np.nan]})
        result = compute_outlier_stats(df, ["x"])
        assert result.iloc[0]["iqr_outlier_count"] == 0
