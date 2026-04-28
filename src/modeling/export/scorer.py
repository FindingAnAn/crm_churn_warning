"""Scorer — predict churn probabilities on all active customers.

Convention: 13-Data_ML §6.3 — inference uses same scaler as training.
Convention: 10-Code_design §3.1 — single-responsibility.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import xgboost as xgb

from data.preprocessing.dataset_prep.sample_weighting import DatasetResult

logger = logging.getLogger(__name__)


def score_all(
    model: xgb.Booster,
    ds: DatasetResult,
    threshold: float,
    top_percentile: float | None = 10.0,
) -> pd.DataFrame:
    """Score all active customers and attach predictions.

    Args:
        model: Trained XGBoost Booster.
        ds: DatasetResult with x_predict (already scaled).
        threshold: Probability threshold for churn classification.

    Returns:
        DataFrame with original metadata + churn_probability + churn_flag.
    """
    dpredict = xgb.DMatrix(ds.x_predict, feature_names=ds.feature_names)
    y_prob = model.predict(dpredict)

    if top_percentile is not None:
        dynamic_threshold = float(np.percentile(y_prob, 100.0 - top_percentile))
        effective_threshold = max(threshold, dynamic_threshold)
        logger.info(
            "Top %.1f%% cutoff requested. Dynamic threshold=%.4f, Original=%.4f",
            top_percentile, dynamic_threshold, threshold,
        )
    else:
        effective_threshold = threshold

    scored = ds.active_df.copy()
    scored["churn_probability"] = y_prob
    scored["churn_flag"] = (y_prob >= effective_threshold).astype(int)

    logger.info(
        "Scored %d customers: effective_threshold=%.4f, flagged=%d (%.1f%%)",
        len(scored), effective_threshold,
        int(scored["churn_flag"].sum()),
        scored["churn_flag"].mean() * 100,
    )
    return scored


def compute_score_stats(scored_df: pd.DataFrame) -> dict:
    """Compute score distribution statistics.

    Args:
        scored_df: DataFrame with 'churn_probability' column.

    Returns:
        Dict with mean, p50, p90, p99, risk_count, active_count, risk_ratio.
    """
    probs = scored_df["churn_probability"].dropna().values

    if len(probs) == 0:
        return {"mean": None, "p50": None, "p90": None, "p99": None}

    risk_count = int(scored_df.get("churn_flag", pd.Series(dtype=int)).sum())
    active_count = len(scored_df)

    return {
        "mean": float(np.mean(probs)),
        "p50": float(np.quantile(probs, 0.50)),
        "p90": float(np.quantile(probs, 0.90)),
        "p99": float(np.quantile(probs, 0.99)),
        "risk_count": risk_count,
        "active_count": active_count,
        "risk_ratio": risk_count / max(active_count, 1),
    }


def compute_reasons(
    scored_df: pd.DataFrame,
    model: xgb.Booster,
    *,
    top_n: int = 3,
) -> pd.DataFrame:
    """Compute top-N feature-based reasons for flagged customers.

    Uses global feature importance (gain) to pick most influential features,
    then labels based on whether each feature is above/below population median.

    Args:
        scored_df: Scored DataFrame with feature columns.
        model: Trained model for feature importance.
        top_n: Number of reasons per customer.

    Returns:
        scored_df with reason_1, reason_2, ..., reason_N columns added.
    """
    importance = model.get_score(importance_type="gain")
    if not importance:
        logger.warning("No feature importance found — skipping reasons")
        return scored_df

    total = sum(importance.values()) or 1.0
    sorted_feats = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    top_feats = [f for f, _ in sorted_feats[:top_n]]

    result = scored_df.copy()
    for i, feat in enumerate(top_feats, start=1):
        col_name = f"reason_{i}"
        if feat in result.columns:
            median_val = result[feat].median()
            result[col_name] = np.where(
                result[feat] > median_val,
                f"High {feat}",
                f"Low {feat}",
            )
        else:
            result[col_name] = f"Feature: {feat}"

    logger.info("Reasons computed using top-%d features: %s", top_n, top_feats)
    return result
