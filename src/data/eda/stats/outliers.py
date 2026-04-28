"""Outlier detection for numeric features.

Provides IQR-based and z-score-based outlier counts per feature.

Convention: 10-Code_design §2.1 — one coherent responsibility.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_outlier_stats(
    df: pd.DataFrame,
    feature_cols: list[str],
    iqr_factor: float = 1.5,
    zscore_threshold: float = 3.0,
) -> pd.DataFrame:
    """Per-feature outlier summary using IQR and z-score methods.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    feature_cols : list[str]
        Columns to analyse.
    iqr_factor : float
        Multiplier for IQR fences (default 1.5).
    zscore_threshold : float
        Absolute z-score cutoff (default 3.0).

    Returns
    -------
    pd.DataFrame
        One row per feature with:
        ``feature_name, iqr_lower, iqr_upper, iqr_outlier_count,
        iqr_outlier_pct, zscore_outlier_count, zscore_outlier_pct``.
    """
    cols = [c for c in feature_cols if c in df.columns]
    rows: list[dict] = []

    for col in cols:
        s = pd.to_numeric(df[col], errors="coerce")
        s_clean = s.replace([np.inf, -np.inf], np.nan).dropna()
        n = len(s_clean)

        row: dict = {"feature_name": col}

        if n == 0 or s_clean.std() == 0:
            row.update(
                iqr_lower=None, iqr_upper=None,
                iqr_outlier_count=0, iqr_outlier_pct=0.0,
                zscore_outlier_count=0, zscore_outlier_pct=0.0,
            )
        else:
            q1 = float(s_clean.quantile(0.25))
            q3 = float(s_clean.quantile(0.75))
            iqr = q3 - q1
            lower = q1 - iqr_factor * iqr
            upper = q3 + iqr_factor * iqr
            iqr_out = int(((s_clean < lower) | (s_clean > upper)).sum())

            mean = float(s_clean.mean())
            std = float(s_clean.std())
            z = np.abs((s_clean - mean) / std)
            z_out = int((z > zscore_threshold).sum())

            row.update(
                iqr_lower=round(lower, 6),
                iqr_upper=round(upper, 6),
                iqr_outlier_count=iqr_out,
                iqr_outlier_pct=round(iqr_out / n, 6),
                zscore_outlier_count=z_out,
                zscore_outlier_pct=round(z_out / n, 6),
            )

        rows.append(row)

    return pd.DataFrame(rows)
