"""Class distribution analysis for binary targets.

Convention: 10-Code_design §2.1 — one coherent responsibility.
"""

from __future__ import annotations

import pandas as pd


def compute_class_distribution(y: pd.Series) -> dict:
    """Compute churn-rate and class imbalance statistics.

    Parameters
    ----------
    y : pd.Series
        Binary target (0/1 or bool).

    Returns
    -------
    dict
        Keys: ``total_count, positive_count, negative_count,
        churn_rate, imbalance_ratio``.
        ``imbalance_ratio`` = negative / positive (inf when no positives).
    """
    y_binary = pd.to_numeric(y, errors="coerce").fillna(0).astype(int)
    total = len(y_binary)
    pos = int((y_binary == 1).sum())
    neg = total - pos
    churn_rate = round(pos / total, 6) if total > 0 else 0.0
    imbalance = round(neg / pos, 4) if pos > 0 else float("inf")
    return {
        "total_count": total,
        "positive_count": pos,
        "negative_count": neg,
        "churn_rate": churn_rate,
        "imbalance_ratio": imbalance,
    }
