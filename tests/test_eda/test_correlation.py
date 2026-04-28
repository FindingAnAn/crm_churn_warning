"""Tests for correlation analysis.

Convention: 07-Testing §3 — Arrange-Act-Assert.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.eda.stats.correlation import (
    compute_correlation_matrix,
    extract_high_correlations,
)


class TestComputeCorrelationMatrix:
    """Verify correlation matrix computation."""

    def test_should_return_identity_diagonal(
        self, sample_df: pd.DataFrame, sample_feature_cols: list[str],
    ) -> None:
        corr = compute_correlation_matrix(sample_df, sample_feature_cols)
        for col in sample_feature_cols:
            assert abs(corr.loc[col, col] - 1.0) < 1e-10

    def test_should_return_high_correlation_when_identical(self) -> None:
        df = pd.DataFrame({"x": [1, 2, 3, 4], "y": [1, 2, 3, 4]})
        corr = compute_correlation_matrix(df, ["x", "y"])
        assert abs(corr.loc["x", "y"] - 1.0) < 1e-10

    def test_should_return_square_matrix(
        self, sample_df: pd.DataFrame, sample_feature_cols: list[str],
    ) -> None:
        corr = compute_correlation_matrix(sample_df, sample_feature_cols)
        assert corr.shape == (3, 3)


class TestExtractHighCorrelations:
    """Verify filtering of high-correlation pairs."""

    def test_should_filter_below_threshold(self) -> None:
        corr = pd.DataFrame(
            [[1.0, 0.9, 0.3], [0.9, 1.0, 0.1], [0.3, 0.1, 1.0]],
            index=["a", "b", "c"],
            columns=["a", "b", "c"],
        )
        result = extract_high_correlations(corr, threshold=0.8)
        assert len(result) == 1
        assert result.iloc[0]["feature_a"] == "a"
        assert result.iloc[0]["feature_b"] == "b"

    def test_should_exclude_self_correlations(self) -> None:
        corr = pd.DataFrame(
            [[1.0, 0.1], [0.1, 1.0]],
            index=["a", "b"],
            columns=["a", "b"],
        )
        result = extract_high_correlations(corr, threshold=0.5)
        assert result.empty

    def test_should_sort_by_absolute_value_descending(self) -> None:
        corr = pd.DataFrame(
            [[1.0, -0.95, 0.85], [-0.95, 1.0, 0.80], [0.85, 0.80, 1.0]],
            index=["a", "b", "c"],
            columns=["a", "b", "c"],
        )
        result = extract_high_correlations(corr, threshold=0.8)
        assert len(result) >= 2
        assert abs(result.iloc[0]["correlation"]) >= abs(
            result.iloc[1]["correlation"],
        )
