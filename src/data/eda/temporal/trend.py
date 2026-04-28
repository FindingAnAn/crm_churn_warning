"""Feature trend detection across monthly snapshots.

Convention: 10-Code_design §2.1 — one coherent responsibility.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_feature_trends(
    dfs_by_month: dict[int, pd.DataFrame],
    feature_cols: list[str],
    p_threshold: float = 0.05,
) -> pd.DataFrame:
    """Detect systematic shifts in feature medians over time.

    For each feature, computes the median per month and fits a linear
    regression (OLS) to detect a trend.

    Parameters
    ----------
    dfs_by_month : dict[int, pd.DataFrame]
        Mapping ``YYMM`` -> DataFrame for each month.
    feature_cols : list[str]
        Features to analyse.
    p_threshold : float
        P-value cutoff for ``is_trending`` flag.

    Returns
    -------
    pd.DataFrame
        Columns: ``feature_name, n_months, slope, r_squared,
        p_value, is_trending``.
        Empty DataFrame when fewer than 3 months are provided.
    """
    sorted_months = sorted(dfs_by_month.keys())
    n_months = len(sorted_months)

    if n_months < 3:
        logger.warning(
            "Trend detection requires >= 3 months; got %d", n_months,
        )
        return pd.DataFrame(
            columns=[
                "feature_name", "n_months", "slope",
                "r_squared", "p_value", "is_trending",
            ],
        )

    x = np.arange(n_months, dtype=float)
    rows: list[dict] = []

    for col in feature_cols:
        medians = []
        for m in sorted_months:
            df_m = dfs_by_month[m]
            if col in df_m.columns:
                s = pd.to_numeric(df_m[col], errors="coerce")
                medians.append(float(s.median()) if not s.dropna().empty else np.nan)
            else:
                medians.append(np.nan)

        y = np.array(medians, dtype=float)
        valid = ~np.isnan(y)
        n_valid = int(valid.sum())

        if n_valid < 3:
            rows.append({
                "feature_name": col,
                "n_months": n_valid,
                "slope": None,
                "r_squared": None,
                "p_value": None,
                "is_trending": False,
            })
            continue

        xv, yv = x[valid], y[valid]
        slope, intercept = np.polyfit(xv, yv, 1)

        # R-squared
        y_pred = slope * xv + intercept
        ss_res = float(np.sum((yv - y_pred) ** 2))
        ss_tot = float(np.sum((yv - yv.mean()) ** 2))
        r_sq = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # P-value via t-test on slope
        if n_valid > 2 and ss_tot > 0:
            se = np.sqrt(ss_res / (n_valid - 2)) / np.sqrt(
                np.sum((xv - xv.mean()) ** 2),
            )
            if se > 0:
                t_stat = slope / se
                # Two-tailed p-value from t-distribution
                from scipy.stats import t as t_dist

                p_val = float(2.0 * t_dist.sf(abs(t_stat), df=n_valid - 2))
            else:
                p_val = 0.0
        else:
            p_val = 1.0

        rows.append({
            "feature_name": col,
            "n_months": n_valid,
            "slope": round(float(slope), 8),
            "r_squared": round(float(r_sq), 6),
            "p_value": round(p_val, 8),
            "is_trending": bool(p_val < p_threshold),
        })

    return pd.DataFrame(rows)
