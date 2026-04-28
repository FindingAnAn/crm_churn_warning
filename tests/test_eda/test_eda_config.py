"""Tests for EdaConfig.

Convention: 07-Testing §3 — test_should_<expected>_when_<condition>.
"""

from __future__ import annotations

import pytest

from data.eda.config import EdaConfig


class TestEdaConfig:
    """Verify EdaConfig validation and serialization."""

    def test_should_pass_validation_when_defaults(self) -> None:
        cfg = EdaConfig()
        cfg.validate()  # no exception

    def test_should_reject_empty_features_when_empty_list(self) -> None:
        cfg = EdaConfig(feature_cols=[])
        with pytest.raises(ValueError, match="feature_cols must not be empty"):
            cfg.validate()

    def test_should_reject_negative_iqr_factor_when_invalid(self) -> None:
        cfg = EdaConfig(outlier_iqr_factor=-1)
        with pytest.raises(ValueError, match="outlier_iqr_factor must be > 0"):
            cfg.validate()

    def test_should_reject_invalid_correlation_method(self) -> None:
        cfg = EdaConfig(correlation_method="kendall")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="correlation_method"):
            cfg.validate()

    def test_should_reject_zero_nbins_when_too_small(self) -> None:
        cfg = EdaConfig(n_bins=1)
        with pytest.raises(ValueError, match="n_bins must be >= 2"):
            cfg.validate()

    def test_should_reject_invalid_woe_min_pct(self) -> None:
        cfg = EdaConfig(woe_min_pct=0.0)
        with pytest.raises(ValueError, match="woe_min_pct"):
            cfg.validate()

    def test_should_reject_zero_temporal_months(self) -> None:
        cfg = EdaConfig(temporal_window_months=0)
        with pytest.raises(ValueError, match="temporal_window_months"):
            cfg.validate()

    def test_should_return_safe_dict_without_feature_list(self) -> None:
        cfg = EdaConfig()
        d = cfg.to_safe_dict()
        assert "n_features" in d
        assert "feature_cols" not in d  # not exposed in safe dict

    def test_should_be_frozen_when_set_attribute(self) -> None:
        cfg = EdaConfig()
        with pytest.raises(AttributeError):
            cfg.n_bins = 20  # type: ignore[misc]
