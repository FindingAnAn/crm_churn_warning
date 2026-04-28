"""Tests for dataset_prep/pipeline_config.py — hyperparameter validation.

Convention: 02-Config §6.1 — config must self-validate.
"""

from __future__ import annotations

import pytest

from data.preprocessing.dataset_prep.pipeline_config import (
    DatasetPipelineConfig,
    NUMERIC_FEATURES,
)


class TestDatasetPipelineConfig:
    """Tests for DatasetPipelineConfig validation."""

    def test_default_config_is_valid(self):
        """Default config should pass validation."""
        cfg = DatasetPipelineConfig()
        cfg.validate()  # Should not raise

    def test_invalid_horizon(self):
        """horizon_months < 1 should be rejected."""
        cfg = DatasetPipelineConfig(horizon_months=0)
        with pytest.raises(ValueError, match="horizon_months"):
            cfg.validate()

    def test_invalid_w_min(self):
        """w_min < 2 should be rejected."""
        cfg = DatasetPipelineConfig(w_min=1)
        with pytest.raises(ValueError, match="w_min"):
            cfg.validate()

    def test_invalid_alpha_ewma_zero(self):
        """alpha_ewma must be in (0, 1)."""
        cfg = DatasetPipelineConfig(alpha_ewma=0.0)
        with pytest.raises(ValueError, match="alpha_ewma"):
            cfg.validate()

    def test_invalid_alpha_ewma_one(self):
        """alpha_ewma must be in (0, 1)."""
        cfg = DatasetPipelineConfig(alpha_ewma=1.0)
        with pytest.raises(ValueError, match="alpha_ewma"):
            cfg.validate()

    def test_invalid_sim_threshold_negative(self):
        """sim_threshold must be in [0, 1]."""
        cfg = DatasetPipelineConfig(sim_threshold=-0.1)
        with pytest.raises(ValueError, match="sim_threshold"):
            cfg.validate()

    def test_invalid_recency_order(self):
        """recency_active must be < recency_at_risk."""
        cfg = DatasetPipelineConfig(recency_active=200, recency_at_risk=100)
        with pytest.raises(ValueError, match="recency_active"):
            cfg.validate()

    def test_to_safe_dict(self):
        """to_safe_dict() returns a logging-safe dictionary."""
        cfg = DatasetPipelineConfig()
        d = cfg.to_safe_dict()
        assert "horizon_months" in d
        assert "alpha_ewma" in d
        assert isinstance(d["data_start"], str)


class TestNumericFeatures:
    """Tests for the NUMERIC_FEATURES constant."""

    def test_features_are_unique(self):
        """Feature names should be unique (no duplicates)."""
        assert len(NUMERIC_FEATURES) == len(set(NUMERIC_FEATURES))

    def test_features_are_snake_case(self):
        """Feature names should follow snake_case convention."""
        for name in NUMERIC_FEATURES:
            assert name == name.lower(), f"Feature '{name}' is not snake_case"
            assert " " not in name, f"Feature '{name}' contains spaces"

    def test_ewma_features_present(self):
        """EWMA features must be in the list."""
        assert "ewma" in NUMERIC_FEATURES
        assert "delta_ewma" in NUMERIC_FEATURES
