"""Model evaluation — compute metrics on the eval set.

Convention: 13-Data_ML §8.1 — metrics at threshold chosen by F1.
Convention: 10-Code_design §3.1 — single-responsibility function.
"""

from __future__ import annotations

import logging

import numpy as np
import xgboost as xgb
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

from data.preprocessing.dataset_prep.sample_weighting import DatasetResult

logger = logging.getLogger(__name__)


def best_threshold_by_fbeta(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    beta: float = 0.5,
) -> float:
    """Find the probability threshold that maximizes F-beta score.

    Args:
        y_true: Ground truth binary labels.
        y_prob: Predicted probabilities.
        beta: Beta value for F-score (beta < 1 favors precision, default 0.5).

    Returns:
        Optimal threshold value.
    """
    prec, rec, thresholds = precision_recall_curve(y_true, y_prob)
    beta_sq = beta**2
    f_scores = (1 + beta_sq) * (prec[:-1] * rec[:-1]) / ((beta_sq * prec[:-1]) + rec[:-1] + 1e-9)
    if len(f_scores) == 0:
        return 0.5
    return float(thresholds[int(np.argmax(f_scores))])


def evaluate_model(
    model: xgb.Booster,
    ds: DatasetResult,
) -> dict:
    """Evaluate model on the held-out eval set (confirmed churners).

    Args:
        model: Trained XGBoost Booster.
        ds: DatasetResult containing x_eval, y_eval.

    Returns:
        Dict with keys: f1, precision, recall, pr_auc, roc_auc, threshold,
        n_eval, n_pos, n_neg.
    """
    deval = xgb.DMatrix(ds.x_eval, feature_names=ds.feature_names)
    y_prob = model.predict(deval)
    y_true = ds.y_eval.values.astype(int)

    threshold = best_threshold_by_fbeta(y_true, y_prob, beta=0.5)
    y_pred = (y_prob >= threshold).astype(int)

    n_pos = int((y_true == 1).sum())
    n_neg = int((y_true == 0).sum())

    metrics = {
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "f05": float(fbeta_score(y_true, y_pred, beta=0.5, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)) if n_pos > 0 and n_neg > 0 else 0.0,
        "threshold": float(threshold),
        "n_eval": len(y_true),
        "n_pos": n_pos,
        "n_neg": n_neg,
    }

    logger.info(
        "Eval metrics: F1=%.4f, F0.5(Precision-focus)=%.4f, PR-AUC=%.4f, threshold=%.4f (%d pos / %d neg)",
        metrics["f1"],
        metrics["f05"],
        metrics["pr_auc"],
        metrics["threshold"],
        n_pos,
        n_neg,
    )
    return metrics
