"""Step 3 — EWMA computation (multi-signal).

Compute Exponentially Weighted Moving Average and delta for multiple
metric signals (item, revenue, complaint, delay, nodone, order,
satisfaction) from monthly pivot columns in feature window tables.

Conventions applied:
  - 13-Data_ML §6.2: Isolated, stateless, independently testable.
  - 13-Data_ML §6.4: Stateless by default — no internal state.
  - 13-Data_ML §9.3: Returns new DataFrame, no in-place modification.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Metric prefixes for multi-signal EWMA.
# Columns follow pattern: {prefix}_t, {prefix}_1m_ago, {prefix}_2m_ago, ...
# or: {prefix}_last, {prefix}_1m_ago, {prefix}_2m_ago, ...
DEFAULT_EWMA_METRICS: list[str] = [
    "item",
    "revenue",
    "complaint",
    "delay",
    "nodone",
    "order",
    "satisfaction",
]


def compute_ewma(
    df: pd.DataFrame,
    window_size: int,
    alpha: float,
    metrics: list[str] | None = None,
) -> pd.DataFrame:
    """Compute EWMA and delta_ewma for multiple metric signals.

    For each metric prefix (e.g. 'item', 'revenue'), finds monthly
    pivot columns ({prefix}_last/t, {prefix}_1m_ago, ...) and computes:
      - ewma_{prefix}: EWMA across the time series (oldest → newest)
      - delta_ewma_{prefix}: ewma_current - ewma_penultimate

    Also produces legacy ``ewma`` and ``delta_ewma`` columns (from item)
    for backward compatibility.

    Args:
        df: Feature DataFrame with monthly pivot columns.
        window_size: Window size W (determines how many monthly cols exist).
        alpha: EWMA smoothing parameter (0 < alpha < 1).
        metrics: List of metric prefixes. Defaults to DEFAULT_EWMA_METRICS.

    Returns:
        DataFrame with ewma_{prefix} and delta_ewma_{prefix} columns added.
    """
    if metrics is None:
        metrics = DEFAULT_EWMA_METRICS

    result = df.copy()

    for prefix in metrics:
        monthly_cols = _find_monthly_cols(result, prefix, window_size)

        if len(monthly_cols) < 2:
            logger.debug(
                "EWMA %s: insufficient monthly columns (%s). Defaulting.",
                prefix,
                monthly_cols,
            )
            # Fallback: use latest value if available
            fallback_col = f"{prefix}_last"
            if fallback_col not in result.columns:
                fallback_col = f"{prefix}_t"
            result[f"ewma_{prefix}"] = result.get(fallback_col, 0)
            result[f"delta_ewma_{prefix}"] = 0.0
            continue

        monthly_data = result[monthly_cols].fillna(0).values  # (N, T)
        ewma_all = _vectorized_ewma_series(monthly_data, alpha)

        # ewma = final value in series
        result[f"ewma_{prefix}"] = ewma_all[:, -1]

        # delta = ewma_current - ewma_penultimate (not raw oldest)
        result[f"delta_ewma_{prefix}"] = ewma_all[:, -1] - ewma_all[:, -2]

        logger.debug(
            "EWMA %s: %d monthly columns processed",
            prefix,
            len(monthly_cols),
        )

    # Legacy compatibility: ewma = ewma_item, delta_ewma = delta_ewma_item
    if "ewma_item" in result.columns:
        result["ewma"] = result["ewma_item"]
        result["delta_ewma"] = result["delta_ewma_item"]

    computed = [m for m in metrics if f"ewma_{m}" in result.columns]
    logger.info("EWMA computed for %d signals: %s", len(computed), computed)

    return result


def _find_monthly_cols(
    df: pd.DataFrame,
    prefix: str,
    window_size: int,
) -> list[str]:
    """Find ordered monthly columns for a metric prefix (oldest first).

    Tries both naming conventions:
      - {prefix}_last, {prefix}_1m_ago, {prefix}_2m_ago, ...
      - {prefix}_t, {prefix}_1m_ago, {prefix}_2m_ago, ...
    """
    cols: list[str] = []

    for offset in range(window_size - 1, -1, -1):
        if offset == 0:
            # Try both "last" and "t" suffixes
            for suffix in ("last", "t"):
                col = f"{prefix}_{suffix}"
                if col in df.columns:
                    cols.append(col)
                    break
        else:
            col = f"{prefix}_{offset}m_ago"
            if col in df.columns:
                cols.append(col)

    return cols


def _vectorized_ewma_series(
    data: np.ndarray,
    alpha: float,
) -> np.ndarray:
    """Compute EWMA across columns, returning full series.

    Args:
        data: 2D array of shape (n_samples, n_months), oldest-first.
        alpha: Smoothing parameter.

    Returns:
        2D array of shape (n_samples, n_months) with EWMA at each step.
    """
    n_samples, n_months = data.shape
    ewma_series = np.zeros_like(data, dtype=float)
    ewma_series[:, 0] = data[:, 0]

    for t in range(1, n_months):
        ewma_series[:, t] = alpha * data[:, t] + (1 - alpha) * ewma_series[:, t - 1]

    return ewma_series


# Backward-compatible alias (used by existing tests)
def _vectorized_ewma(data: np.ndarray, alpha: float) -> np.ndarray:
    """Compute EWMA across columns (oldest → newest). Returns final values."""
    return _vectorized_ewma_series(data, alpha)[:, -1]
