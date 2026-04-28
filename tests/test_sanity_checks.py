"""Tests for sanity checks module.

Convention: 13-Data_ML §3.3 — fail early on data quality issues.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import StandardScaler

from data.preprocessing.dataset_prep.sample_weighting import DatasetResult
from data.preprocessing.dataset_prep.sanity_checks import run_sanity_checks


def _make_dataset_result(
    n_train: int = 100,
    n_eval: int = 10,
    n_features: int = 5,
    churn_rate: float = 0.15,
    eval_ids: set | None = None,
) -> tuple[DatasetResult, set[str]]:
    """Helper to build a synthetic DatasetResult for testing."""
    feature_names = [f"feat_{i}" for i in range(n_features)]
    if eval_ids is None:
        eval_ids = {f"EVAL_{i}" for i in range(n_eval)}

    np.random.seed(42)

    # Train set
    x_train = pd.DataFrame(
        np.random.randn(n_train, n_features), columns=feature_names
    )
    y_train = pd.Series(
        np.random.choice([0.0, 1.0], size=n_train, p=[1 - churn_rate, churn_rate])
    )
    w_train = pd.Series(np.ones(n_train) * 0.5)

    # Eval set
    x_eval = pd.DataFrame(
        np.random.randn(n_eval, n_features), columns=feature_names
    )
    y_eval = pd.Series(np.ones(n_eval))  # All churners

    # Active set (train + eval)
    train_ids = [f"TRAIN_{i}" for i in range(n_train)]
    eval_list = list(eval_ids)
    active_df = pd.DataFrame({"cms_code_enc": train_ids + eval_list})

    scaler = StandardScaler()
    scaler.fit(x_train)

    result = DatasetResult(
        x_train=x_train,
        y_train=y_train,
        w_train=w_train,
        x_eval=x_eval,
        y_eval=y_eval,
        x_predict=pd.concat([x_train, x_eval], ignore_index=True),
        scaler=scaler,
        feature_names=feature_names,
        active_df=active_df,
    )
    return result, eval_ids


class TestSanityChecks:
    """Tests for run_sanity_checks."""

    def test_valid_dataset_passes(self):
        """A well-formed dataset should pass all checks."""
        result, eval_ids = _make_dataset_result()
        assert run_sanity_checks(result, eval_ids) is True

    def test_nan_weights_fail(self):
        """NaN in sample weights should raise ValueError."""
        result, eval_ids = _make_dataset_result()
        result.w_train.iloc[0] = np.nan
        with pytest.raises(ValueError, match="Weight NaN"):
            run_sanity_checks(result, eval_ids)

    def test_nan_features_fail(self):
        """NaN in X_train should raise ValueError."""
        result, eval_ids = _make_dataset_result()
        result.x_train.iloc[0, 0] = np.nan
        with pytest.raises(ValueError, match="Feature NaN"):
            run_sanity_checks(result, eval_ids)

    def test_extreme_churn_rate_warns(self):
        """Churn rate outside 1%–60% should warn but not raise."""
        result, eval_ids = _make_dataset_result(churn_rate=0.001)
        # Forces all y_train = 0 (below 1% threshold)
        result.y_train[:] = 0.0
        # Should not raise (non-critical) but return False
        passed = run_sanity_checks(result, eval_ids)
        assert passed is False
