"""Tests for scorer — compute_score_stats and compute_reasons.

Convention: 10-Code_design §3.1 — single-responsibility functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from modeling.export.scorer import compute_reasons, compute_score_stats


class TestComputeScoreStats:
    """Tests for compute_score_stats (pure pandas)."""

    def test_basic_stats(self):
        df = pd.DataFrame({
            "churn_probability": [0.1, 0.3, 0.5, 0.7, 0.9],
            "churn_flag": [0, 0, 0, 1, 1],
        })
        stats = compute_score_stats(df)
        assert stats["active_count"] == 5
        assert stats["risk_count"] == 2
        assert abs(stats["mean"] - 0.5) < 1e-6
        assert abs(stats["risk_ratio"] - 0.4) < 1e-6

    def test_p50_is_median(self):
        df = pd.DataFrame({
            "churn_probability": [0.1, 0.3, 0.5, 0.7, 0.9],
            "churn_flag": [0, 0, 0, 1, 1],
        })
        stats = compute_score_stats(df)
        assert abs(stats["p50"] - 0.5) < 1e-6

    def test_p90_and_p99(self):
        probs = np.linspace(0, 1, 100)
        df = pd.DataFrame({
            "churn_probability": probs,
            "churn_flag": (probs >= 0.5).astype(int),
        })
        stats = compute_score_stats(df)
        assert stats["p90"] > stats["p50"]
        assert stats["p99"] > stats["p90"]

    def test_all_flagged(self):
        df = pd.DataFrame({
            "churn_probability": [0.8, 0.9],
            "churn_flag": [1, 1],
        })
        stats = compute_score_stats(df)
        assert stats["risk_count"] == 2
        assert stats["risk_ratio"] == 1.0

    def test_none_flagged(self):
        df = pd.DataFrame({
            "churn_probability": [0.1, 0.2],
            "churn_flag": [0, 0],
        })
        stats = compute_score_stats(df)
        assert stats["risk_count"] == 0
        assert stats["risk_ratio"] == 0.0

    def test_empty_dataframe(self):
        df = pd.DataFrame({"churn_probability": pd.Series(dtype=float)})
        stats = compute_score_stats(df)
        assert stats["mean"] is None
        assert stats["p50"] is None

    def test_single_row(self):
        df = pd.DataFrame({
            "churn_probability": [0.42],
            "churn_flag": [1],
        })
        stats = compute_score_stats(df)
        assert stats["active_count"] == 1
        assert stats["risk_count"] == 1
        assert abs(stats["mean"] - 0.42) < 1e-6

    def test_without_churn_flag_column(self):
        """Should handle missing churn_flag gracefully."""
        df = pd.DataFrame({"churn_probability": [0.5, 0.6]})
        stats = compute_score_stats(df)
        assert stats["risk_count"] == 0
        assert stats["active_count"] == 2


class TestComputeReasons:
    """Tests for compute_reasons (needs mock model)."""

    def _mock_model(self, importance: dict):
        """Create a mock XGBoost model with given feature importance."""
        model = MagicMock()
        model.get_score.return_value = importance
        return model

    def test_adds_reason_columns(self):
        df = pd.DataFrame({
            "feat_a": [10, 20, 30],
            "feat_b": [5, 15, 25],
            "feat_c": [1, 2, 3],
        })
        model = self._mock_model({"feat_a": 100, "feat_b": 50, "feat_c": 10})
        result = compute_reasons(df, model, top_n=3)
        assert "reason_1" in result.columns
        assert "reason_2" in result.columns
        assert "reason_3" in result.columns

    def test_reason_values_high_low(self):
        df = pd.DataFrame({
            "feat_a": [10, 20, 30],
        })
        model = self._mock_model({"feat_a": 100})
        result = compute_reasons(df, model, top_n=1)
        # median of [10,20,30] = 20
        # row 0: 10 <= 20 → "Low feat_a"
        # row 2: 30 > 20 → "High feat_a"
        assert result["reason_1"].iloc[0] == "Low feat_a"
        assert result["reason_1"].iloc[2] == "High feat_a"

    def test_top_n_limits_reasons(self):
        df = pd.DataFrame({
            "feat_a": [1, 2],
            "feat_b": [3, 4],
            "feat_c": [5, 6],
        })
        model = self._mock_model({"feat_a": 100, "feat_b": 50, "feat_c": 10})
        result = compute_reasons(df, model, top_n=2)
        assert "reason_1" in result.columns
        assert "reason_2" in result.columns
        assert "reason_3" not in result.columns

    def test_missing_feature_column(self):
        """Features in importance but not in df → fallback label."""
        df = pd.DataFrame({"other_col": [1, 2]})
        model = self._mock_model({"missing_feat": 100})
        result = compute_reasons(df, model, top_n=1)
        assert result["reason_1"].iloc[0] == "Feature: missing_feat"

    def test_empty_importance(self):
        """Empty importance → return df unchanged."""
        df = pd.DataFrame({"feat_a": [1, 2]})
        model = self._mock_model({})
        result = compute_reasons(df, model, top_n=3)
        assert "reason_1" not in result.columns

    def test_does_not_modify_input(self):
        df = pd.DataFrame({"feat_a": [1, 2, 3]})
        original_cols = list(df.columns)
        model = self._mock_model({"feat_a": 100})
        _ = compute_reasons(df, model, top_n=1)
        assert list(df.columns) == original_cols
