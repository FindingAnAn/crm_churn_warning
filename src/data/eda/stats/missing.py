"""Missing-value analysis for numeric features.

Convention: 10-Code_design §2.1 — one coherent responsibility per function.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd


def compute_missing_stats(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:
    """Per-feature missing-value and infinity summary.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    feature_cols : list[str]
        Columns to analyse (non-existent columns are skipped).

    Returns
    -------
    pd.DataFrame
        One row per feature:
        ``feature_name, total_count, missing_count, missing_pct, has_inf``.
    """
    cols = [c for c in feature_cols if c in df.columns]
    rows: list[dict] = []
    total = len(df)

    for col in cols:
        s = df[col]
        s_num = pd.to_numeric(s, errors="coerce")
        n_missing = int(s_num.isna().sum())
        has_inf = bool(np.isinf(s_num).any()) if s_num.dtype.kind == "f" else False
        rows.append({
            "feature_name": col,
            "total_count": total,
            "missing_count": n_missing,
            "missing_pct": round(n_missing / total, 6) if total > 0 else 0.0,
            "has_inf": has_inf,
        })

    return pd.DataFrame(rows)


def compute_missing_pattern(
    df: pd.DataFrame,
    feature_cols: list[str],
    top_n: int = 10,
) -> list[dict]:
    """Identify the most common co-missing patterns.

    Each "pattern" is a set of columns that are simultaneously null in
    the same rows.  Returns the *top_n* most frequent patterns.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    feature_cols : list[str]
        Columns to analyse.
    top_n : int
        Number of patterns to return.

    Returns
    -------
    list[dict]
        Each dict has: ``pattern_hash, affected_columns, row_count,
        pct_of_total``.
    """
    cols = [c for c in feature_cols if c in df.columns]
    if not cols:
        return []

    null_mask = df[cols].isnull()
    # Only keep rows that have at least one null
    any_null = null_mask.any(axis=1)
    null_subset = null_mask.loc[any_null]

    if null_subset.empty:
        return []

    total = len(df)
    # Build a hashable signature per row
    patterns: dict[str, dict] = {}

    for _, row in null_subset.iterrows():
        missing_cols = tuple(c for c in cols if row[c])
        if not missing_cols:
            continue
        key = hashlib.md5(
            ",".join(missing_cols).encode()
        ).hexdigest()[:12]
        if key not in patterns:
            patterns[key] = {
                "pattern_hash": key,
                "affected_columns": list(missing_cols),
                "row_count": 0,
            }
        patterns[key]["row_count"] += 1

    result = sorted(
        patterns.values(), key=lambda p: p["row_count"], reverse=True,
    )[:top_n]

    for p in result:
        p["pct_of_total"] = round(p["row_count"] / total, 6) if total > 0 else 0.0

    return result
