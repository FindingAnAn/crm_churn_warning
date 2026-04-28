"""Feature-target relationship analysis: point-biserial & WoE/IV.

Convention: 10-Code_design §2.1 — one coherent responsibility.
Convention: 13-Data_ML §6.1 — snake_case feature names.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist


# ── Point-biserial correlation ──────────────────────────
def compute_point_biserial(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
) -> pd.DataFrame:
    """Point-biserial correlation between features and binary target.

    Mathematically equivalent to Pearson r on a binary variable.
    P-value uses the t-test transformation:
    ``t = r * sqrt(n-2) / sqrt(1-r^2)``.

    Parameters
    ----------
    df : pd.DataFrame
        Input data with features and target.
    feature_cols : list[str]
        Numeric feature columns.
    target_col : str
        Binary target column.

    Returns
    -------
    pd.DataFrame
        Columns: ``feature_name, correlation, p_value``.
    """
    cols = [c for c in feature_cols if c in df.columns]
    if target_col not in df.columns or not cols:
        return pd.DataFrame(
            columns=["feature_name", "correlation", "p_value"],
        )

    target = pd.to_numeric(df[target_col], errors="coerce")
    rows: list[dict] = []

    for col in cols:
        feat = pd.to_numeric(df[col], errors="coerce")
        valid = feat.notna() & target.notna()
        n = int(valid.sum())
        if n < 3:
            rows.append({
                "feature_name": col, "correlation": None, "p_value": None,
            })
            continue

        r = float(feat[valid].corr(target[valid]))
        if np.isnan(r) or abs(r) >= 1.0:
            p_val = 0.0 if abs(r) >= 1.0 else None
        else:
            t_stat = r * np.sqrt(n - 2) / np.sqrt(1 - r ** 2)
            p_val = float(2.0 * t_dist.sf(abs(t_stat), df=n - 2))

        rows.append({
            "feature_name": col,
            "correlation": round(r, 6),
            "p_value": round(p_val, 8) if p_val is not None else None,
        })

    return pd.DataFrame(rows)


# ── Weight of Evidence / Information Value ───────────────
def compute_woe_iv(
    df: pd.DataFrame,
    feature_col: str,
    target_col: str,
    n_bins: int = 10,
    min_pct: float = 0.05,
) -> tuple[pd.DataFrame, float]:
    """WoE and IV for a single feature vs. binary target.

    Quantile-based binning with Laplace smoothing for zero-count bins.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    feature_col : str
        Numeric feature column.
    target_col : str
        Binary target column (1 = event/churn).
    n_bins : int
        Number of quantile bins.
    min_pct : float
        Minimum bin proportion guard (unused — Laplace handles edge).

    Returns
    -------
    tuple[pd.DataFrame, float]
        Bin-level WoE table and total IV.
    """
    feat = pd.to_numeric(df[feature_col], errors="coerce")
    target = pd.to_numeric(df[target_col], errors="coerce")
    valid = feat.notna() & target.notna()
    feat_v = feat[valid].reset_index(drop=True)
    target_v = target[valid].reset_index(drop=True)

    if feat_v.empty:
        return pd.DataFrame(), 0.0

    # Quantile binning
    try:
        bins = pd.qcut(feat_v, q=n_bins, duplicates="drop")
    except ValueError:
        bins = pd.cut(feat_v, bins=max(2, n_bins), duplicates="drop")

    grouped = pd.DataFrame({"bin": bins, "target": target_v})
    agg = grouped.groupby("bin", observed=True)["target"].agg(
        ["sum", "count"],
    )
    agg.columns = ["event", "total"]
    agg["non_event"] = agg["total"] - agg["event"]

    # Laplace smoothing (0.5)
    eps = 0.5
    total_event = agg["event"].sum()
    total_non = agg["non_event"].sum()

    if total_event == 0 or total_non == 0:
        return pd.DataFrame(), 0.0

    agg["dist_event"] = (agg["event"] + eps) / (total_event + eps * len(agg))
    agg["dist_non"] = (agg["non_event"] + eps) / (total_non + eps * len(agg))
    agg["woe"] = np.log(agg["dist_non"] / agg["dist_event"])
    agg["iv_bin"] = (agg["dist_non"] - agg["dist_event"]) * agg["woe"]

    iv = float(agg["iv_bin"].sum())
    result = agg.reset_index()
    result["bin"] = result["bin"].astype(str)
    return result, round(iv, 6)


def _iv_strength(iv: float) -> str:
    """Classify IV into strength categories."""
    if iv < 0.02:
        return "useless"
    if iv < 0.10:
        return "weak"
    if iv < 0.30:
        return "medium"
    if iv < 0.50:
        return "strong"
    return "suspicious"


def compute_all_woe_iv(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    n_bins: int = 10,
    min_pct: float = 0.05,
) -> pd.DataFrame:
    """Compute IV summary for all features.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    feature_cols : list[str]
        Numeric feature columns.
    target_col : str
        Binary target column.
    n_bins : int
        Number of quantile bins.
    min_pct : float
        Minimum bin proportion.

    Returns
    -------
    pd.DataFrame
        Columns: ``feature_name, iv, iv_strength``.
    """
    cols = [c for c in feature_cols if c in df.columns]
    rows: list[dict] = []

    for col in cols:
        _, iv = compute_woe_iv(df, col, target_col, n_bins, min_pct)
        rows.append({
            "feature_name": col,
            "iv": round(iv, 6),
            "iv_strength": _iv_strength(iv),
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("iv", ascending=False).reset_index(
            drop=True,
        )
    return result
