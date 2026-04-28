"""Tests for EWMA computation — stateless, vectorized.

Convention: 13-Data_ML §6.2 — functions are stateless & testable in isolation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.preprocessing.dataset_prep.ewma import compute_ewma, _vectorized_ewma


class TestVectorizedEwma:
    """Tests for _vectorized_ewma (NumPy-only)."""

    def test_single_column(self):
        """Single column should return the column itself."""
        data = np.array([[10.0], [20.0], [30.0]])
        result = _vectorized_ewma(data, alpha=0.3)
        np.testing.assert_array_equal(result, [10.0, 20.0, 30.0])

    def test_two_columns_manual(self):
        """Verify EWMA formula: ewma = alpha * new + (1-alpha) * old."""
        data = np.array([[10.0, 20.0]])
        result = _vectorized_ewma(data, alpha=0.3)
        expected = 0.3 * 20.0 + 0.7 * 10.0  # = 13.0
        np.testing.assert_almost_equal(result[0], expected)

    def test_three_columns(self):
        """Three time periods with known values."""
        data = np.array([[100.0, 200.0, 300.0]])
        alpha = 0.5
        result = _vectorized_ewma(data, alpha)
        # Step 1: ewma = 100
        # Step 2: ewma = 0.5*200 + 0.5*100 = 150
        # Step 3: ewma = 0.5*300 + 0.5*150 = 225
        np.testing.assert_almost_equal(result[0], 225.0)

    def test_batch_dimension(self):
        """Should handle multiple rows independently."""
        data = np.array([
            [10.0, 20.0],
            [100.0, 0.0],
        ])
        result = _vectorized_ewma(data, alpha=0.5)
        expected = np.array([15.0, 50.0])
        np.testing.assert_array_almost_equal(result, expected)


class TestComputeEwma:
    """Tests for compute_ewma (DataFrame interface)."""

    def test_adds_ewma_columns(self):
        """Should add multi-signal ewma columns."""
        df = pd.DataFrame({
            "cms_code_enc": ["A", "B"],
            "item_last": [10, 20],
            "item_1m_ago": [15, 25],
            "item_2m_ago": [20, 30],
        })
        result = compute_ewma(df, window_size=3, alpha=0.3)
        # Multi-signal columns
        assert "ewma_item" in result.columns
        assert "delta_ewma_item" in result.columns
        # Legacy aliases
        assert "ewma" in result.columns
        assert "delta_ewma" in result.columns
        assert len(result) == 2

    def test_multi_signal_ewma(self):
        """Should compute EWMA for multiple metric signals."""
        df = pd.DataFrame({
            "item_last": [10],
            "item_1m_ago": [15],
            "revenue_last": [100],
            "revenue_1m_ago": [200],
            "complaint_last": [1],
            "complaint_1m_ago": [3],
        })
        result = compute_ewma(
            df, window_size=2, alpha=0.3,
            metrics=["item", "revenue", "complaint"],
        )
        assert "ewma_item" in result.columns
        assert "ewma_revenue" in result.columns
        assert "ewma_complaint" in result.columns
        assert "delta_ewma_revenue" in result.columns

    def test_delta_ewma_penultimate(self):
        """delta_ewma should be ewma_current - ewma_penultimate."""
        df = pd.DataFrame({
            "item_last": [30],
            "item_1m_ago": [20],
            "item_2m_ago": [10],
        })
        result = compute_ewma(df, window_size=3, alpha=0.5)
        # ewma_series: [10, 0.5*20+0.5*10=15, 0.5*30+0.5*15=22.5]
        # delta = 22.5 - 15.0 = 7.5
        np.testing.assert_almost_equal(
            result["delta_ewma_item"].iloc[0], 7.5
        )

    def test_does_not_modify_input(self):
        """Should return a new DataFrame, not modify input in-place."""
        df = pd.DataFrame({
            "item_last": [10],
            "item_1m_ago": [15],
        })
        original_cols = list(df.columns)
        _ = compute_ewma(df, window_size=2, alpha=0.3)
        assert list(df.columns) == original_cols

    def test_insufficient_columns_fallback(self):
        """With < 2 monthly columns, should default to item_last."""
        df = pd.DataFrame({
            "item_last": [42],
        })
        result = compute_ewma(df, window_size=1, alpha=0.3)
        assert result["ewma_item"].iloc[0] == 42
        assert result["delta_ewma_item"].iloc[0] == 0.0
        # Legacy alias
        assert result["ewma"].iloc[0] == 42
        assert result["delta_ewma"].iloc[0] == 0.0

    def test_t_suffix_convention(self):
        """Should handle _t suffix (alternative naming)."""
        df = pd.DataFrame({
            "order_t": [5],
            "order_1m_ago": [10],
        })
        result = compute_ewma(df, window_size=2, alpha=0.5, metrics=["order"])
        assert "ewma_order" in result.columns
        assert "delta_ewma_order" in result.columns
