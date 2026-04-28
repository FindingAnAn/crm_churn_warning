"""Tests for descriptive statistics.

Convention: 07-Testing §3 — Arrange-Act-Assert.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.eda.stats.descriptive import compute_descriptive_stats


class TestComputeDescriptiveStats:
    """Verify descriptive statistics computation."""

    def test_should_return_correct_mean_when_uniform_data(
        self, sample_df: pd.DataFrame, sample_feature_cols: list[str],
    ) -> None:
        result = compute_descriptive_stats(sample_df, sample_feature_cols)
        row_a = result[result["feature_name"] == "feat_a"].iloc[0]
        # feat_a = 1..200, mean = 100.5
        assert abs(row_a["mean"] - 100.5) < 0.01

    def test_should_compute_skew_when_skewed_distribution(
        self, sample_df: pd.DataFrame, sample_feature_cols: list[str],
    ) -> None:
        result = compute_descriptive_stats(sample_df, sample_feature_cols)
        row_a = result[result["feature_name"] == "feat_a"].iloc[0]
        # uniform distribution has skew ~ 0
        assert abs(row_a["skew"]) < 0.5

    def test_should_return_correct_percentiles(
        self, sample_df: pd.DataFrame, sample_feature_cols: list[str],
    ) -> None:
        result = compute_descriptive_stats(
            sample_df, sample_feature_cols, [0.25, 0.50, 0.75],
        )
        row_a = result[result["feature_name"] == "feat_a"].iloc[0]
        assert abs(row_a["p50"] - 100.5) < 1.0

    def test_should_handle_all_nan_column_when_feature_missing(self) -> None:
        df = pd.DataFrame({"x": [np.nan, np.nan, np.nan]})
        result = compute_descriptive_stats(df, ["x"])
        assert result.iloc[0]["mean"] is None
        assert result.iloc[0]["count"] == 0

    def test_should_ignore_nonexistent_columns(
        self, sample_df: pd.DataFrame,
    ) -> None:
        result = compute_descriptive_stats(sample_df, ["no_such_col"])
        assert result.empty

    def test_should_return_one_row_per_feature(
        self, sample_df: pd.DataFrame, sample_feature_cols: list[str],
    ) -> None:
        result = compute_descriptive_stats(sample_df, sample_feature_cols)
        assert len(result) == 3
