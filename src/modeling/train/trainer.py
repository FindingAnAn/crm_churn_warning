"""XGBoost trainer — consumes DatasetResult from dataset_prep.

Convention: 13-Data_ML §6.3 — scaler fitted on train only (done by dataset_prep).
Convention: 13-Data_ML §9.1 — idempotent pipeline step.
Convention: 10-Code_design §3.1 — single-responsibility function.
"""

from __future__ import annotations

import logging

import xgboost as xgb

from data.preprocessing.dataset_prep.sample_weighting import DatasetResult
from modeling.config.model_config import ModelConfig

logger = logging.getLogger(__name__)


def train_model(
    ds: DatasetResult,
    config: ModelConfig,
) -> xgb.Booster:
    """Train an XGBoost model on the prepared dataset.

    Args:
        ds: DatasetResult from the dataset preparation pipeline.
        config: Model training configuration.

    Returns:
        Trained XGBoost Booster.

    Raises:
        ValueError: If training data is empty or has no positive labels.
    """
    config.validate()

    if ds.x_train.empty:
        raise ValueError("x_train is empty — cannot train")

    pos_count = int((ds.y_train > 0.5).sum())
    neg_count = len(ds.y_train) - pos_count
    if pos_count == 0:
        raise ValueError("No positive labels in y_train — cannot train")

    logger.info(
        "Training XGBoost: %d samples (%d pos / %d neg), %d features",
        len(ds.y_train),
        pos_count,
        neg_count,
        len(ds.feature_names),
    )

    dtrain = xgb.DMatrix(
        ds.x_train,
        label=ds.y_train,
        weight=ds.w_train,
        feature_names=ds.feature_names,
    )
    deval = xgb.DMatrix(
        ds.x_eval,
        label=ds.y_eval,
        feature_names=ds.feature_names,
    )

    params = config.to_xgb_params()

    model = xgb.train(
        params,
        dtrain,
        num_boost_round=config.n_estimators,
        evals=[(dtrain, "train"), (deval, "eval")],
        early_stopping_rounds=config.early_stopping_rounds,
        verbose_eval=50,
    )

    logger.info(
        "Training complete. Best iteration: %d, best score: %.6f",
        model.best_iteration,
        model.best_score,
    )
    return model


def get_feature_importance(
    model: xgb.Booster,
    importance_type: str = "gain",
) -> dict[str, float]:
    """Extract feature importance from trained model.

    Args:
        model: Trained XGBoost Booster.
        importance_type: One of 'weight', 'gain', 'cover',
            'total_gain', 'total_cover'.

    Returns:
        Dict mapping feature name to importance score, sorted descending.
    """
    raw = model.get_score(importance_type=importance_type)
    total = sum(raw.values()) or 1.0
    normalized = {k: v / total for k, v in raw.items()}
    return dict(sorted(normalized.items(), key=lambda x: x[1], reverse=True))
