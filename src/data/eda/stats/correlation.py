"""Feature-feature correlation analysis.

Convention: 10-Code_design §2.1 — one coherent responsibility.
"""

from __future__ import annotations

import pandas as pd


def compute_correlation_matrix(
    df: pd.DataFrame,
    feature_cols: list[str],
    method: str = "pearson",
) -> pd.DataFrame:
    """Compute the full NxN correlation matrix.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    feature_cols : list[str]
        Columns to include.
    method : str
        ``"pearson"`` or ``"spearman"``.

    Returns
    -------
    pd.DataFrame
        Square correlation matrix (feature x feature).
    """
    cols = [c for c in feature_cols if c in df.columns]
    return df[cols].corr(method=method)


def extract_high_correlations(
    corr_matrix: pd.DataFrame,
    threshold: float = 0.80,
) -> pd.DataFrame:
    """Extract feature pairs whose |correlation| >= *threshold*.

    Self-correlations are excluded.  Results are sorted by absolute
    value descending.

    Parameters
    ----------
    corr_matrix : pd.DataFrame
        Square correlation matrix.
    threshold : float
        Minimum absolute correlation.

    Returns
    -------
    pd.DataFrame
        Columns: ``feature_a, feature_b, correlation``.
    """
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    features = corr_matrix.columns.tolist()

    for i, fa in enumerate(features):
        for j, fb in enumerate(features):
            if i >= j:
                continue
            val = corr_matrix.iloc[i, j]
            if pd.isna(val):
                continue
            if abs(val) >= threshold:
                pair = (fa, fb) if fa < fb else (fb, fa)
                if pair not in seen:
                    seen.add(pair)
                    rows.append({
                        "feature_a": pair[0],
                        "feature_b": pair[1],
                        "correlation": round(float(val), 6),
                    })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            "correlation", key=lambda x: x.abs(), ascending=False,
        ).reset_index(drop=True)
    return result
