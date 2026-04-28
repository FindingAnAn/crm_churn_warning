"""Shared fixtures for EDA tests.

Convention: 07-Testing §5.1 — reusable fixtures for test setup.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture()
def sample_feature_cols() -> list[str]:
    """Three simple feature column names."""
    return ["feat_a", "feat_b", "feat_c"]


@pytest.fixture()
def sample_df(sample_feature_cols: list[str]) -> pd.DataFrame:
    """DataFrame with known values for deterministic assertions.

    - feat_a: uniform [1..100]
    - feat_b: normally distributed (mean=50, std=10)
    - feat_c: contains 10 % NaN + 2 extreme outliers
    """
    rng = np.random.RandomState(42)
    n = 200

    a = np.arange(1, n + 1, dtype=float)
    b = rng.normal(50, 10, size=n).round(2)

    c = rng.normal(30, 5, size=n).round(2)
    # Inject NaN
    nan_idx = rng.choice(n, size=20, replace=False)
    c[nan_idx] = np.nan
    # Inject outliers
    c[0] = 999.0
    c[1] = -999.0

    return pd.DataFrame({
        "feat_a": a,
        "feat_b": b,
        "feat_c": c,
    })


@pytest.fixture()
def sample_target() -> pd.Series:
    """Binary target with ~20 % churn rate."""
    rng = np.random.RandomState(42)
    y = rng.choice([0, 1], size=200, p=[0.8, 0.2])
    return pd.Series(y, name="target")


@pytest.fixture()
def sample_df_with_target(
    sample_df: pd.DataFrame,
    sample_target: pd.Series,
) -> pd.DataFrame:
    """sample_df augmented with a 'target' column."""
    df = sample_df.copy()
    df["target"] = sample_target.values
    return df


@pytest.fixture()
def monthly_dfs(sample_feature_cols: list[str]) -> dict[int, pd.DataFrame]:
    """Three monthly snapshots with slight distribution shift."""
    rng = np.random.RandomState(42)
    result: dict[int, pd.DataFrame] = {}

    for i, yymm in enumerate([2501, 2502, 2503]):
        shift = i * 5  # progressive shift
        n = 150
        result[yymm] = pd.DataFrame({
            "feat_a": rng.normal(50 + shift, 10, n).round(2),
            "feat_b": rng.normal(30 + shift, 8, n).round(2),
            "feat_c": rng.normal(20, 5, n).round(2),
        })

    return result
