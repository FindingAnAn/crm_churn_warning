"""Step 4b — Walk-forward validation for window size selection.

Find the optimal window size W* by running expanding-window
walk-forward validation with a logistic regression baseline.

Conventions applied:
  - 13-Data_ML §8.3: Compare against baseline before selecting.
  - 13-Data_ML §8.4: Metrics logged per fold/split.
  - 13-Data_ML §7.3: Random state controlled via seed parameter.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from data.preprocessing.dataset_prep.label_construction import (
    build_training_windows,
)
from data.preprocessing.dataset_prep.pipeline_config import NUMERIC_FEATURES

logger = logging.getLogger(__name__)


def walkforward_auc(
    engine: Any,
    window_size: int,
    all_months: pd.DatetimeIndex,
    horizon_months: int,
    alpha_ewma: float,
    min_train_windows: int,
    random_seed: int = 42,
) -> dict[str, Any]:
    """Run walk-forward expanding window validation for one W.

    Uses a LogisticRegression baseline to compute AUC per fold.

    Args:
        engine: SQLAlchemy engine.
        window_size: Window size W.
        all_months: All months in data range.
        horizon_months: Prediction horizon H.
        alpha_ewma: EWMA smoothing parameter.
        min_train_windows: Minimum training windows before first fold.
        random_seed: Random state for reproducibility.

    Returns:
        Dict with keys: W, auc (mean), n_folds, auc_per_fold.
    """
    training_data = build_training_windows(engine, window_size, all_months, horizon_months, alpha_ewma)

    if training_data.empty:
        return {"W": window_size, "auc": None, "n_folds": 0}

    window_ids = sorted(training_data["_end_month"].unique())
    n_windows = len(window_ids)
    n_folds = n_windows - min_train_windows

    if n_folds <= 0:
        logger.warning(
            "W=%d: insufficient windows (%d) for walk-forward",
            window_size,
            n_windows,
        )
        return {"W": window_size, "auc": None, "n_folds": 0}

    feats = [f for f in NUMERIC_FEATURES if f in training_data.columns]
    auc_scores: list[float] = []

    for fold in range(n_folds):
        train_windows = window_ids[: min_train_windows + fold]
        val_window = window_ids[min_train_windows + fold]

        train_fold = training_data[training_data["_end_month"].isin(train_windows)]
        val_fold = training_data[training_data["_end_month"] == val_window]

        x_train = train_fold[feats].fillna(0)
        y_train = train_fold["y_raw"]
        x_val = val_fold[feats].fillna(0)
        y_val = val_fold["y_raw"]

        # Skip fold if only one class present
        if y_val.nunique() < 2:
            continue

        pipe = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "lr",
                    LogisticRegression(
                        C=1.0,
                        class_weight="balanced",
                        max_iter=500,
                        random_state=random_seed,
                    ),
                ),
            ]
        )
        pipe.fit(x_train, y_train)
        y_prob = pipe.predict_proba(x_val)[:, 1]
        auc = roc_auc_score(y_val, y_prob)
        auc_scores.append(auc)

        logger.debug(
            "W=%d Fold %d: train=[%s..%s] val=%s AUC=%.4f",
            window_size,
            fold + 1,
            train_windows[0].strftime("%y%m"),
            train_windows[-1].strftime("%y%m"),
            val_window.strftime("%y%m"),
            auc,
        )

    mean_auc = float(np.mean(auc_scores)) if auc_scores else None

    logger.info(
        "W=%d walk-forward: mean_auc=%.4f (%d folds)",
        window_size,
        mean_auc or 0.0,
        len(auc_scores),
    )

    return {
        "W": window_size,
        "auc": mean_auc,
        "n_folds": len(auc_scores),
        "auc_per_fold": auc_scores,
    }


def find_best_w(
    engine: Any,
    w_search: list[int],
    all_months: pd.DatetimeIndex,
    horizon_months: int,
    alpha_ewma: float,
    min_train_windows: int,
    random_seed: int = 42,
) -> int:
    """Search for the optimal window size W* via walk-forward AUC.

    Args:
        engine: SQLAlchemy engine.
        w_search: List of W values to evaluate.
        all_months: All months in data range.
        horizon_months: Prediction horizon H.
        alpha_ewma: EWMA smoothing parameter.
        min_train_windows: Minimum training windows per fold.
        random_seed: Random state.

    Returns:
        W* (window size with highest mean walk-forward AUC).
    """
    results: dict[int, float | None] = {}

    for w in w_search:
        logger.info("Walk-forward W=%d:", w)
        r = walkforward_auc(
            engine,
            w,
            all_months,
            horizon_months,
            alpha_ewma,
            min_train_windows,
            random_seed,
        )
        results[w] = r["auc"]

    valid = {w: auc for w, auc in results.items() if auc is not None}

    if valid:
        w_star = max(valid, key=valid.get)  # type: ignore[arg-type]
        logger.info("W* = %d (AUC=%.4f)", w_star, valid[w_star])
        return w_star

    # Fallback to minimum W
    w_star = min(w_search)
    logger.warning("Fallback W* = %d (no valid walk-forward results)", w_star)
    return w_star
