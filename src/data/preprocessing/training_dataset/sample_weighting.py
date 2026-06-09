"""Step 7 — Sample weighting and label smoothing.

Apply sample weights and label smoothing to produce the final
training dataset (X_train, y_train, w_train, X_eval, y_eval).

"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


@dataclass
class DatasetResult:
    """Final dataset output from the preparation pipeline.

    Attributes:
        x_train: Scaled training features.
        y_train: Smoothed training labels.
        w_train: Sample weights.
        x_eval: Scaled evaluation features (confirmed holdout plus optional
            assumed-negative unlabeled rows).
        y_eval: Evaluation labels. Confirmed holdout rows are ground truth;
            unlabeled rows are assumed negatives.
        x_predict: Scaled features for all active accounts.
        scaler: Fitted StandardScaler (for inference reuse).
        feature_names: List of feature column names.
        active_df: Full active DataFrame with all metadata.
    """

    x_train: pd.DataFrame
    y_train: pd.Series
    w_train: pd.Series
    x_eval: pd.DataFrame
    y_eval: pd.Series
    x_predict: pd.DataFrame
    scaler: StandardScaler
    feature_names: list[str]
    active_df: pd.DataFrame


LEAKAGE_FEATURE_KEYWORDS: tuple[str, ...] = (
    "y_raw",
    "y_label",
    "y_smooth",
    "label",
    "target",
    "churn",
    "item_in_horizon",
    "rev_in_horizon",
    "future",
)


def split_confirmed_ids(
    confirmed_ids: set[str],
    eval_holdout_frac: float,
    random_seed: int,
) -> tuple[set[str], set[str]]:
    """Split confirmed churn IDs into train/prototype and eval holdout sets.

    The holdout IDs must not be used to build the prototype or train the model.
    This prevents label leakage from the CSKH-confirmed set into evaluation.
    """
    if not confirmed_ids or eval_holdout_frac <= 0:
        return set(confirmed_ids), set()

    ids = np.array(sorted(confirmed_ids), dtype=object)
    n_eval = max(1, int(round(len(ids) * eval_holdout_frac)))
    n_eval = min(n_eval, len(ids) - 1) if len(ids) > 1 else 0
    if n_eval <= 0:
        return set(confirmed_ids), set()

    rng = np.random.default_rng(random_seed)
    eval_idx = set(rng.choice(len(ids), size=n_eval, replace=False).tolist())
    eval_ids = {str(ids[i]) for i in eval_idx}
    train_ids = set(confirmed_ids) - eval_ids
    return train_ids, eval_ids


def apply_weights_and_smoothing(
    df: pd.DataFrame,
    pu_weight_c: float,
    label_smooth_eps_confirmed: float,
    label_smooth_eps_pseudo: float,
) -> pd.DataFrame:
    """Apply sample weights and label smoothing.

    Args:
        df: DataFrame with ``label_source`` column.
        pu_weight_c: PU learning weight for unlabeled samples.
        label_smooth_eps_confirmed: Smoothing epsilon for confirmed.
        label_smooth_eps_pseudo: Smoothing epsilon for pseudo/unlabeled.

    Returns:
        DataFrame with ``y_label``, ``sample_weight``, ``y_smooth`` added.
    """
    result = df.copy()

    # Raw binary labels
    label_map = {
        "confirmed": 1.0,
        "confirmed_eval": 1.0,
        "pseudo_churn": 1.0,
        "reliable_neg": 0.0,
        "pu_unlabeled": 0.0,
    }
    result["y_label"] = result["label_source"].map(label_map)

    # Sample weights
    weight_map = {
        "confirmed": 1.0,
        "confirmed_eval": 0.0,
        "pseudo_churn": 0.50,
        "reliable_neg": 0.80,
        "pu_unlabeled": pu_weight_c,
    }
    result["sample_weight"] = result["label_source"].map(weight_map)

    # Label smoothing: y_smooth = (1 - ε) * y + ε * 0.5
    eps_map = {
        "confirmed": label_smooth_eps_confirmed,
        "confirmed_eval": label_smooth_eps_confirmed,
        "pseudo_churn": label_smooth_eps_pseudo,
        "reliable_neg": label_smooth_eps_pseudo,
        "pu_unlabeled": label_smooth_eps_pseudo,
    }
    eps_series = result["label_source"].map(eps_map)
    result["y_smooth"] = (1 - eps_series) * result["y_label"] + eps_series * 0.5

    return result


def build_final_dataset(
    active_df: pd.DataFrame,
    training_history_df: pd.DataFrame | set[str] | None = None,
    eval_ids: set[str] | list[str] | None = None,
    feature_names: list[str] | None = None,
    *,
    random_seed: int = 42,
    eval_unlabeled_frac: float = 0.20,
) -> DatasetResult:
    """Build the final train/eval/predict datasets with scaling.

    Scaler is fit ONLY on the training set (convention 13-Data_ML §6.3).

    Args:
        active_df: DataFrame with ``y_smooth``, ``y_label``,
            ``sample_weight``, ``cms_code_enc`` columns.
        training_history_df: Historical rows with time-aware ``y_raw``.
            For backward compatibility, callers may omit this argument.
        eval_ids: Confirmed churn holdout IDs (used for eval split only).
        feature_names: List of numeric feature columns.
        random_seed: Reproducible seed for unlabeled eval sampling.
        eval_unlabeled_frac: Fraction of unlabeled rows sampled as assumed
            negative eval rows.

    Returns:
        DatasetResult containing all splits and the fitted scaler.
    """
    # Backward-compatible call shape:
    # build_final_dataset(active_df, eval_ids, feature_names)
    if feature_names is None and isinstance(training_history_df, set | list) and isinstance(eval_ids, list):
        feature_names = list(eval_ids)
        eval_ids = set(training_history_df)
        training_history_df = None

    history_df = training_history_df if isinstance(training_history_df, pd.DataFrame) else pd.DataFrame()
    eval_id_set = set(eval_ids or set())
    if feature_names is None:
        raise ValueError("feature_names must be provided")

    feats = [f for f in feature_names if f in active_df.columns]
    _validate_no_leakage_features(feats)

    # PU Learning Architecture:
    # 1. Confirmed eval IDs MUST NEVER be used in training (strict holdout).
    is_eval_confirmed = active_df["cms_code_enc"].isin(eval_id_set)

    # 2. Split unlabeled/pseudo-labeled rows to provide assumed negatives for evaluation.
    unlabeled_df = active_df[~is_eval_confirmed]
    eval_unlabeled_idx = _sample_unlabeled_eval_index(
        unlabeled_df,
        eval_unlabeled_frac,
        random_seed,
    )
    is_eval_unlabeled = active_df.index.isin(eval_unlabeled_idx)

    train_mask = ~(is_eval_confirmed | is_eval_unlabeled)
    eval_mask = is_eval_confirmed | is_eval_unlabeled

    active_with_split = active_df.copy()
    active_with_split["_dataset_split"] = "train"
    active_with_split.loc[eval_mask, "_dataset_split"] = "eval"

    x_train_active = active_with_split.loc[train_mask, feats].fillna(0)
    y_train_active = active_with_split.loc[train_mask, "y_smooth"]
    w_train_active = active_with_split.loc[train_mask, "sample_weight"]

    # Historical rows must use their own forward horizon label only.
    # Do not mark current confirmed CSKH IDs as churn in every past window.
    if not history_df.empty:
        y_train_hist = (history_df["y_raw"] == 1).astype(float)
        w_train_hist = pd.Series(1.0, index=history_df.index)

        # Ensure only available features are used and missing filled with 0
        hist_features = history_df.copy()
        for feat in (f for f in feats if f not in hist_features.columns):
            hist_features[feat] = 0.0

        x_train_hist = hist_features[feats].fillna(0)

        x_train_raw = pd.concat([x_train_active, x_train_hist], ignore_index=True)
        y_train = pd.concat([y_train_active, y_train_hist], ignore_index=True)
        w_train = pd.concat([w_train_active, w_train_hist], ignore_index=True)

        logger.info(
            "Merged %d historical training samples (true labels: sum(y)=%d) into Training Set",
            len(x_train_hist),
            int(y_train_hist.sum()),
        )
    else:
        x_train_raw = x_train_active
        y_train = y_train_active
        w_train = w_train_active

    x_eval_raw = active_with_split.loc[eval_mask, feats].fillna(0)
    y_eval = active_with_split.loc[eval_mask, "y_label"]  # No smoothing for GT

    # Fit scaler on train set ONLY (prevent data leakage)
    scaler = StandardScaler()
    x_train = pd.DataFrame(scaler.fit_transform(x_train_raw), columns=feats, index=x_train_raw.index)
    x_eval = pd.DataFrame(scaler.transform(x_eval_raw), columns=feats, index=x_eval_raw.index)
    x_predict = pd.DataFrame(
        scaler.transform(active_with_split[feats].fillna(0)),
        columns=feats,
        index=active_with_split.index,
    )

    logger.info(
        "Final dataset: X_train=%s, X_eval=%s, X_predict=%s",
        x_train.shape,
        x_eval.shape,
        x_predict.shape,
    )
    logger.info(
        "Train churn rate: %.2f%%, weight range: [%.4f, %.4f]",
        (y_train > 0.5).mean() * 100,
        w_train.min(),
        w_train.max(),
    )

    return DatasetResult(
        x_train=x_train,
        y_train=y_train,
        w_train=w_train,
        x_eval=x_eval,
        y_eval=y_eval,
        x_predict=x_predict,
        scaler=scaler,
        feature_names=feats,
        active_df=active_with_split,
    )


def _sample_unlabeled_eval_index(
    unlabeled_df: pd.DataFrame,
    eval_unlabeled_frac: float,
    random_seed: int,
) -> pd.Index:
    """Sample eval rows from unlabeled data with safe stratification fallback."""
    if unlabeled_df.empty or eval_unlabeled_frac <= 0:
        return pd.Index([])
    if len(unlabeled_df) < 2:
        return pd.Index([])

    stratify = unlabeled_df["y_label"] if unlabeled_df["y_label"].nunique() > 1 else None
    if stratify is not None and stratify.value_counts().min() < 2:
        stratify = None

    _, eval_df = train_test_split(
        unlabeled_df,
        test_size=eval_unlabeled_frac,
        random_state=random_seed,
        stratify=stratify,
    )
    return eval_df.index


def _validate_no_leakage_features(feature_names: list[str]) -> None:
    """Reject target, horizon, and future-derived columns as model features."""
    leaked = [
        name
        for name in feature_names
        if any(keyword in name.lower() for keyword in LEAKAGE_FEATURE_KEYWORDS)
    ]
    if leaked:
        raise ValueError(f"Potential data leakage features are not allowed: {leaked}")
