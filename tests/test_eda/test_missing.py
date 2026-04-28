"""Tests for missing-value analysis.

Convention: 07-Testing §3 — Arrange-Act-Assert.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.eda.stats.missing import compute_missing_pattern, compute_missing_stats


class TestComputeMissingStats:
    """Verify per-feature missing statistics."""

    def test_should_return_zero_missing_when_no_nulls(self) -> None:
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        result = compute_missing_stats(df, ["x", "y"])
        assert all(result["missing_count"] == 0)
        assert all(result["missing_pct"] == 0.0)

    def test_should_return_100pct_when_all_null(self) -> None:
        df = pd.DataFrame({"x": [np.nan, np.nan, np.nan]})
        result = compute_missing_stats(df, ["x"])
        assert result.iloc[0]["missing_pct"] == 1.0

    def test_should_detect_inf_values_when_present(self) -> None:
        df = pd.DataFrame({"x": [1.0, np.inf, -np.inf, 4.0]})
        result = compute_missing_stats(df, ["x"])
        assert result.iloc[0]["has_inf"] is True

    def test_should_count_partial_nulls(
        self, sample_df: pd.DataFrame, sample_feature_cols: list[str],
    ) -> None:
        result = compute_missing_stats(sample_df, sample_feature_cols)
        row_c = result[result["feature_name"] == "feat_c"].iloc[0]
        # feat_c has 20 NaN values out of 200
        assert row_c["missing_count"] == 20
        assert abs(row_c["missing_pct"] - 0.1) < 0.01


class TestComputeMissingPattern:
    """Verify co-missing pattern detection."""

    def test_should_identify_cooccurring_nulls(self) -> None:
        df = pd.DataFrame({
            "a": [1, np.nan, np.nan, 4],
            "b": [1, np.nan, np.nan, 4],
            "c": [1, 2, np.nan, 4],
        })
        patterns = compute_missing_pattern(df, ["a", "b", "c"])
        assert len(patterns) >= 1
        # Most common pattern: a+b missing together
        top = patterns[0]
        assert top["row_count"] >= 1

    def test_should_return_empty_when_no_nulls(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        patterns = compute_missing_pattern(df, ["a", "b"])
        assert patterns == []
