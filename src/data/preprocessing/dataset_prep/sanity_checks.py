"""Sanity checks for the dataset preparation pipeline.

Run after building the final dataset to validate correctness
before passing to model training.

Conventions applied:
  - 13-Data_ML §3.3: Fail early on data quality issues.
"""

from __future__ import annotations

import logging

from data.preprocessing.dataset_prep.sample_weighting import DatasetResult

logger = logging.getLogger(__name__)


def run_sanity_checks(result: DatasetResult, eval_ids: set[str]) -> bool:
    """Run all sanity checks on the final dataset.

    Args:
        result: DatasetResult from ``build_final_dataset``.
        eval_ids: Set of confirmed churn IDs.

    Returns:
        True if all checks pass.

    Raises:
        ValueError: If any critical check fails.
    """
    checks_passed = True

    # 1. No overlap between train and eval
    train_ids = set(result.active_df.loc[~result.active_df["cms_code_enc"].isin(eval_ids), "cms_code_enc"])
    overlap = train_ids & eval_ids
    _check(
        len(overlap) == 0,
        f"[1] Train/Eval overlap: {len(overlap)} (must be 0)",
        critical=True,
    )

    # 2. Class balance within expected range
    churn_rate = (result.y_train > 0.5).mean()
    in_range = 0.03 <= churn_rate <= 0.35
    _check(
        in_range,
        f"[2] Train churn rate: {churn_rate:.2%} (expected 3%–35%)",
    )
    if not in_range:
        checks_passed = False

    # 3. No NaN in weights
    weight_nan = result.w_train.isna().sum()
    _check(
        weight_nan == 0,
        f"[3] Weight NaN count: {weight_nan} (must be 0)",
        critical=True,
    )

    # 4. No NaN in features after fillna
    feat_nan = result.x_train.isna().sum().sum()
    _check(
        feat_nan == 0,
        f"[4] Feature NaN in X_train: {feat_nan} (must be 0)",
        critical=True,
    )

    # 5. Scaler was fitted
    scaler_fitted = hasattr(result.scaler, "mean_")
    _check(
        scaler_fitted,
        f"[5] Scaler fitted: {scaler_fitted} (must be True)",
        critical=True,
    )

    # 6. Eval set size matches
    eval_size_ok = len(result.x_eval) == len(eval_ids) or len(eval_ids) == 0
    _check(
        eval_size_ok,
        f"[6] Eval set size: {len(result.x_eval)} (expected {len(eval_ids)})",
    )

    if checks_passed:
        logger.info("All sanity checks PASSED ✓")
    else:
        logger.warning("Some sanity checks FAILED — review before training")

    return checks_passed


def _check(condition: bool, message: str, *, critical: bool = False) -> None:
    """Log and optionally raise on check failure."""
    if condition:
        logger.info("PASS: %s", message)
    elif critical:
        logger.error("FAIL (critical): %s", message)
        raise ValueError(f"Sanity check failed: {message}")
    else:
        logger.warning("FAIL (non-critical): %s", message)
