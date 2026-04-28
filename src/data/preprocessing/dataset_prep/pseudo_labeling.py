"""Step 6 — Pseudo-labeling.

Assign pseudo-labels to active-tier customers based on
similarity scores, EWMA trends, and confirmed CSKH data.

Conventions applied:
  - 13-Data_ML §6.2: Stateless function.
  - 13-Data_ML §9.3: Returns new DataFrame.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from data.preprocessing.dataset_prep.leading_prototype import (
    compute_similarity,
)

logger = logging.getLogger(__name__)


def assign_pseudo_labels(
    active_df: pd.DataFrame,
    prototype: dict[str, Any],
    eval_ids: set[str],
    sim_threshold: float,
    recency_reliable_neg: int,
    trend_down_ratio: float = 0.85,
) -> pd.DataFrame:
    """Assign pseudo-labels to active-tier accounts.

    Label sources:
      - ``confirmed``: In CSKH eval set (y=1 ground truth).
      - ``pseudo_churn``: High similarity + declining EWMA + declining trend.
      - ``reliable_neg``: Low recency + stable/growing EWMA (y=0).
      - ``pu_unlabeled``: Everything else.

    Args:
        active_df: DataFrame of active-tier accounts (must have ewma,
            delta_ewma, recency_days, item_avg, item_last columns).
        prototype: Prototype dict from ``build_leading_prototype``.
        eval_ids: Set of confirmed churn CMS codes.
        sim_threshold: Threshold for similarity-based pseudo-churn.
        recency_reliable_neg: Max recency_days for reliable negative.
        trend_down_ratio: Ratio threshold for trend_down condition
            (item_last < item_avg * ratio). Default 0.85.

    Returns:
        DataFrame with ``sim_score``, ``label_source`` columns added.
    """
    result = active_df.copy()

    # Compute similarity scores
    result["sim_score"] = compute_similarity(result, prototype)

    # ── Pseudo-churn conditions ────────────────────────────
    sim_high = result["sim_score"] > sim_threshold
    ewma_down = result["delta_ewma"] < 0

    # Trend down: item_last < trend_down_ratio * item_avg
    if "item_last" in result.columns:
        trend_down = (result["item_avg"] > 0) & (result["item_last"] < result["item_avg"] * trend_down_ratio)
    else:
        trend_down = ewma_down

    pseudo_churn = sim_high & ewma_down & trend_down

    # ── Reliable negative conditions ──────────────────────
    reliable_neg = (result["recency_days"] <= recency_reliable_neg) & (result["delta_ewma"] >= 0)

    # ── Assign labels ─────────────────────────────────────
    result["label_source"] = "pu_unlabeled"
    result.loc[pseudo_churn, "label_source"] = "pseudo_churn"
    result.loc[reliable_neg, "label_source"] = "reliable_neg"

    # Override with confirmed (eval set — highest priority)
    result.loc[result["cms_code_enc"].isin(eval_ids), "label_source"] = "confirmed"

    label_counts = result["label_source"].value_counts()
    logger.info("Pseudo-label distribution: %s", label_counts.to_dict())

    pseudo_rate = pseudo_churn.sum() / len(result) if len(result) > 0 else 0.0
    logger.info("Pseudo-churn rate: %.2f%%", pseudo_rate * 100)

    return result
