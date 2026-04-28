"""Tests for ModelConfig — validation, serialization, XGBoost params.

Convention: 02-Config §6.1 — self-validating config.
"""

from __future__ import annotations

import pytest

from modeling.config.model_config import ModelConfig


class TestModelConfigDefaults:
    """Default config should be valid and well-formed."""

    def test_default_is_valid(self):
        cfg = ModelConfig()
        cfg.validate()  # should not raise

    def test_default_max_depth(self):
        assert ModelConfig().max_depth == 6

    def test_default_learning_rate(self):
        assert ModelConfig().learning_rate == 0.05

    def test_default_scale_pos_weight_is_one(self):
        """PU weights handled via sample_weight, not scale_pos_weight."""
        assert ModelConfig().scale_pos_weight == 1.0

    def test_default_eval_metric(self):
        assert ModelConfig().eval_metric == ["logloss", "aucpr"]


class TestModelConfigValidation:
    """validate() should reject invalid hyperparameters."""

    def test_invalid_max_depth_zero(self):
        cfg = ModelConfig(max_depth=0)
        with pytest.raises(ValueError, match="max_depth"):
            cfg.validate()

    def test_invalid_max_depth_negative(self):
        cfg = ModelConfig(max_depth=-3)
        with pytest.raises(ValueError, match="max_depth"):
            cfg.validate()

    def test_invalid_learning_rate_zero(self):
        cfg = ModelConfig(learning_rate=0.0)
        with pytest.raises(ValueError, match="learning_rate"):
            cfg.validate()

    def test_invalid_learning_rate_negative(self):
        cfg = ModelConfig(learning_rate=-0.1)
        with pytest.raises(ValueError, match="learning_rate"):
            cfg.validate()

    def test_invalid_learning_rate_above_one(self):
        cfg = ModelConfig(learning_rate=1.5)
        with pytest.raises(ValueError, match="learning_rate"):
            cfg.validate()

    def test_valid_learning_rate_one(self):
        """learning_rate=1.0 should be valid (boundary)."""
        cfg = ModelConfig(learning_rate=1.0)
        cfg.validate()

    def test_invalid_n_estimators_zero(self):
        cfg = ModelConfig(n_estimators=0)
        with pytest.raises(ValueError, match="n_estimators"):
            cfg.validate()

    def test_invalid_subsample_zero(self):
        cfg = ModelConfig(subsample=0.0)
        with pytest.raises(ValueError, match="subsample"):
            cfg.validate()

    def test_invalid_subsample_above_one(self):
        cfg = ModelConfig(subsample=1.5)
        with pytest.raises(ValueError, match="subsample"):
            cfg.validate()

    def test_invalid_colsample_bytree_zero(self):
        cfg = ModelConfig(colsample_bytree=0.0)
        with pytest.raises(ValueError, match="colsample_bytree"):
            cfg.validate()

    def test_invalid_risk_threshold_negative(self):
        cfg = ModelConfig(risk_threshold_pct=-1.0)
        with pytest.raises(ValueError, match="risk_threshold_pct"):
            cfg.validate()

    def test_invalid_risk_threshold_above_100(self):
        cfg = ModelConfig(risk_threshold_pct=101.0)
        with pytest.raises(ValueError, match="risk_threshold_pct"):
            cfg.validate()

    def test_valid_risk_threshold_boundaries(self):
        """0 and 100 should both be valid."""
        ModelConfig(risk_threshold_pct=0.0).validate()
        ModelConfig(risk_threshold_pct=100.0).validate()


class TestModelConfigSerialization:
    """to_xgb_params() and to_safe_dict() output validation."""

    def test_to_xgb_params_has_objective(self):
        params = ModelConfig().to_xgb_params()
        assert params["objective"] == "binary:logistic"

    def test_to_xgb_params_has_seed(self):
        cfg = ModelConfig(random_state=99)
        params = cfg.to_xgb_params()
        assert params["seed"] == 99

    def test_to_xgb_params_keys(self):
        params = ModelConfig().to_xgb_params()
        expected_keys = {
            "objective", "eval_metric", "max_depth", "learning_rate",
            "subsample", "colsample_bytree", "min_child_weight",
            "gamma", "reg_alpha", "reg_lambda", "scale_pos_weight",
            "seed", "verbosity",
        }
        assert set(params.keys()) == expected_keys

    def test_to_safe_dict_no_sensitive_keys(self):
        """safe_dict should not expose internal details."""
        safe = ModelConfig().to_safe_dict()
        assert "reg_alpha" not in safe
        assert "reg_lambda" not in safe
        assert "gamma" not in safe

    def test_to_safe_dict_has_key_params(self):
        safe = ModelConfig().to_safe_dict()
        assert "max_depth" in safe
        assert "learning_rate" in safe
        assert "n_estimators" in safe
        assert "risk_threshold_pct" in safe

    def test_to_xgb_params_reflects_custom_values(self):
        cfg = ModelConfig(max_depth=10, learning_rate=0.1, subsample=0.5)
        params = cfg.to_xgb_params()
        assert params["max_depth"] == 10
        assert params["learning_rate"] == 0.1
        assert params["subsample"] == 0.5
