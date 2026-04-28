"""Descriptive statistics for numeric features.

Convention: 10-Code_design §2.1 — one coherent responsibility per function.
Convention: 13-Data_ML §6.1 — snake_case feature names.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_descriptive_stats(
    df: pd.DataFrame,
    feature_cols: list[str],
    percentiles: list[float] | None = None,
) -> pd.DataFrame:
    """Compute distribution summary for each numeric feature.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    feature_cols : list[str]
        Columns to analyse (non-existent columns are skipped).
    percentiles : list[float] | None
        Quantiles to report, e.g. ``[0.05, 0.25, 0.50, 0.75, 0.95]``.

    Returns
    -------
    pd.DataFrame
        One row per feature with columns:
        ``feature_name, count, mean, median, std, skew, kurtosis,
        min_val, max_val, p<N>...``
    """
    if percentiles is None:
        percentiles = [0.05, 0.25, 0.50, 0.75, 0.95]

    cols = [c for c in feature_cols if c in df.columns]
    rows: list[dict] = []

    for col in cols:
        s = pd.to_numeric(df[col], errors="coerce")
        s_clean = s.replace([np.inf, -np.inf], np.nan).dropna()

        row: dict = {"feature_name": col, "count": int(len(s_clean))}

        if s_clean.empty:
            row.update(
                mean=None, median=None, std=None, skew=None,
                kurtosis=None, min_val=None, max_val=None,
            )
            for p in percentiles:
                row[f"p{int(p * 100)}"] = None
        else:
            row["mean"] = float(s_clean.mean())
            row["median"] = float(s_clean.median())
            row["std"] = float(s_clean.std())
            row["skew"] = float(s_clean.skew())
            row["kurtosis"] = float(s_clean.kurtosis())
            row["min_val"] = float(s_clean.min())
            row["max_val"] = float(s_clean.max())
            for p in percentiles:
                row[f"p{int(p * 100)}"] = float(np.nanquantile(s_clean, p))

        rows.append(row)

    return pd.DataFrame(rows)
