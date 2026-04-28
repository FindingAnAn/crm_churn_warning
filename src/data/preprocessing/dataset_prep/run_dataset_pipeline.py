"""Dataset preparation pipeline orchestrator.

Single entry point that runs Steps 1→7 in sequence, producing
the final DatasetResult ready for model training.

Supports **fallback mode** when CSKH file is unavailable:
- Uses cached prototype from previous successful run.
- Pipeline still produces valid pseudo-labels and scores.
- eval_ids will be empty → model evaluation is skipped downstream.

Conventions applied:
  - 13-Data_ML §9.1: Each step is idempotent.
  - 13-Data_ML §9.2: Step boundaries are explicit.
  - 13-Data_ML §9.4: Pipeline config externalized.
  - 01-Structure §6.2: Application layer orchestrates workflow.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

import pandas as pd

from data.preprocessing.dataset_prep.activity_tiering import (
    assign_tiers,
    compute_recency,
    detect_t_obs,
)
from data.preprocessing.dataset_prep.cskh_loader import (
    load_eval_ids_from_db,
    scan_and_load_cskh_dir,
)
from data.preprocessing.dataset_prep.ewma import compute_ewma
from data.preprocessing.dataset_prep.label_construction import (
    build_training_windows,
    load_window_features,
)
from data.preprocessing.dataset_prep.leading_prototype import (
    build_leading_prototype,
)
from data.preprocessing.dataset_prep.pipeline_config import (
    NUMERIC_FEATURES,
    DatasetPipelineConfig,
)
from data.preprocessing.dataset_prep.prototype_cache import (
    load_latest_prototype,
    save_prototype,
)
from data.preprocessing.dataset_prep.pseudo_labeling import (
    assign_pseudo_labels,
)
from data.preprocessing.dataset_prep.sample_weighting import (
    DatasetResult,
    apply_weights_and_smoothing,
    build_final_dataset,
)
from data.preprocessing.dataset_prep.sanity_checks import run_sanity_checks
from data.preprocessing.dataset_prep.scope_filter import (
    load_eval_ids,
    load_working_set,
)
from data.preprocessing.dataset_prep.walkforward import find_best_w

logger = logging.getLogger(__name__)


def _compute_run_month(t_obs: pd.Timestamp) -> int:
    """Convert observation timestamp to YYMM integer."""
    return t_obs.year % 100 * 100 + t_obs.month


def run_dataset_pipeline(
    engine: Any,
    config: DatasetPipelineConfig,
    output_dir: Path | None = None,
) -> DatasetResult:
    """Run the full dataset preparation pipeline.

    Steps:
        1. Scope filter → working set + load CSKH (file → DB → eval_ids)
        2. Activity tiering → active / at_risk / churned
        3. EWMA computation → trend features
        4. Walk-forward W* search → optimal window size
        5. Leading prototype → μ_lead, Σ_lead (with fallback)
        6. Pseudo-labeling → label sources
        7. Sample weighting → final X_train, y_train, w_train

    Args:
        engine: SQLAlchemy engine instance.
        config: Pipeline configuration.
        output_dir: Optional directory to save pipeline artifacts.

    Returns:
        DatasetResult containing all splits and artifacts.
        The ``fallback_mode`` flag is attached to the result's active_df
        as metadata column ``_fallback_mode``.
    """
    config.validate()
    logger.info("Pipeline config: %s", config.to_safe_dict())

    # ── Step 1: Scope filter + CSKH loading ───────────────
    logger.info("═" * 60)
    logger.info("STEP 1: Scope filter + CSKH loading")
    working_df = load_working_set(engine, config.min_lifetime_orders)
    working_ids = set(working_df["cms_code_enc"].astype(str))

    # 1a. Scan and load any new CSKH CSV files → DB
    if config.cskh_dir and Path(config.cskh_dir).exists():
        logger.info("Scanning CSKH directory: %s", config.cskh_dir)
        load_results = scan_and_load_cskh_dir(engine, Path(config.cskh_dir))
        for fname, n_rows in load_results.items():
            logger.info("  %s → %d rows", fname, n_rows)

    # 1b. Load eval_ids: try file first, then DB
    eval_ids = load_eval_ids(config.cskh_file_path, working_ids)
    if not eval_ids:
        logger.info("No eval_ids from file — trying DB (cskh.confirmed_churners)")
        eval_ids = load_eval_ids_from_db(engine, working_ids)

    has_cskh = len(eval_ids) > 0
    logger.info(
        "CSKH result: %d confirmed IDs loaded (has_cskh=%s)",
        len(eval_ids),
        has_cskh,
    )

    # ── Step 2: Activity tiering ──────────────────────────
    logger.info("═" * 60)
    logger.info("STEP 2: Activity tiering")
    data_start = pd.Timestamp(config.data_start)
    t_obs = detect_t_obs(
        engine,
        data_start,
        pd.Timestamp(config.t_obs_override) if config.t_obs_override else None,
    )
    working_df = compute_recency(engine, working_df, t_obs, data_start)
    working_df = assign_tiers(working_df, config.recency_active, config.recency_at_risk)

    # Compute PU weight
    n_confirmed = len(eval_ids)
    tier_counts = working_df["tier"].value_counts()
    n_active = tier_counts.get("active", 0)

    if n_confirmed > 0:
        n_unlabeled = max(n_active - n_confirmed, 1)
        pu_weight_c = n_confirmed / n_unlabeled
        pu_weight_c = max(pu_weight_c, config.pu_weight_min)
    else:
        # Fallback: dùng giá trị ước lượng khi không có CSKH
        pu_weight_c = config.fallback_pu_weight
        logger.warning(
            "No confirmed churners — using fallback PU weight: %.4f",
            pu_weight_c,
        )

    logger.info(
        "PU_WEIGHT_C = %.4f (n_confirmed=%d, n_active=%d)",
        pu_weight_c,
        n_confirmed,
        n_active,
    )

    # ── Step 3: Load predict window + EWMA ────────────────
    logger.info("═" * 60)
    logger.info("STEP 3: Load features + EWMA")
    all_months = pd.date_range(data_start, t_obs, freq="MS")
    t_obs_end = t_obs - pd.DateOffset(months=1)

    predict_window_df = load_window_features(engine, config.w_min, t_obs_end)
    if predict_window_df.empty:
        raise RuntimeError(f"Cannot load predict window for W={config.w_min} at {t_obs_end.date()}")
    predict_window_df = compute_ewma(predict_window_df, config.w_min, config.alpha_ewma)

    # ── Step 4: Walk-forward → W* ─────────────────────────
    logger.info("═" * 60)
    logger.info("STEP 4: Walk-forward W* search")
    n_months = len(all_months)
    w_max = max(
        config.w_min,
        n_months - config.horizon_months - config.min_train_windows + 1,
    )
    w_search = list(range(config.w_min, w_max + 1))
    w_star = find_best_w(
        engine,
        w_search,
        all_months,
        config.horizon_months,
        config.alpha_ewma,
        config.min_train_windows,
    )

    if w_star != config.w_min:
        predict_window_df = load_window_features(engine, w_star, t_obs_end)
        predict_window_df = compute_ewma(predict_window_df, w_star, config.alpha_ewma)

    logger.info("Fetching historical training windows for W*=%d", w_star)
    training_history_df = build_training_windows(
        engine, w_star, all_months, config.horizon_months, config.alpha_ewma, config.min_train_windows
    )

    # ── Step 5: Leading prototype (with fallback) ─────────
    logger.info("═" * 60)
    logger.info("STEP 5: Leading prototype")

    run_month = _compute_run_month(t_obs)
    fallback_mode = False

    # 5a. Try to build new prototype from CSKH data
    prototype = build_leading_prototype(
        engine,
        eval_ids,
        t_obs,
        w_star,
        config.alpha_ewma,
        config.sigma_reg,
        min_prototype_samples=config.min_prototype_samples,
    )

    if prototype:
        #  Success → cache to DB
        logger.info("Prototype built successfully — caching to DB")
        save_prototype(engine, prototype, run_month, config.horizon_months)
    else:
        #  Cannot build → try cached fallback
        logger.warning("Cannot build new prototype — attempting fallback")

        if not config.allow_prototype_fallback:
            raise RuntimeError(
                "No prototype available and fallback is disabled (allow_prototype_fallback=False). Provide CSKH data."
            )

        prototype = load_latest_prototype(
            engine,
            horizon=config.horizon_months,
            max_age_months=config.max_prototype_age_months,
            current_month=run_month,
        )

        if prototype:
            fallback_mode = True
            logger.warning(
                "FALLBACK MODE: Using cached prototype from run_month=%d "
                "(n_confirmed=%d, cached_at=%s). "
                "Pseudo-labeling will proceed with cached similarity params.",
                prototype["cached_run_month"],
                prototype["n_confirmed"],
                prototype.get("cached_at", "unknown"),
            )
        else:
            raise RuntimeError(
                "No CSKH data AND no cached prototype available. "
                "Pipeline requires at least one successful run with "
                "CSKH data first. Place CSV files (Roi_bo_MM_YY.csv) "
                "in the CSKH directory and retry."
            )

    # ── Step 6: Pseudo-labeling ───────────────────────────
    logger.info("═" * 60)
    logger.info(
        "STEP 6: Pseudo-labeling%s",
        " (FALLBACK MODE)" if fallback_mode else "",
    )

    # Merge with working_df to get tier + recency
    active_df = predict_window_df.merge(
        working_df[["cms_code_enc", "tier", "recency_days"]],
        on="cms_code_enc",
        how="inner",
    )
    active_df = active_df[active_df["tier"] == "active"].copy()
    logger.info("Active accounts to score: %d", len(active_df))

    active_df = assign_pseudo_labels(
        active_df,
        prototype,
        eval_ids,
        config.sim_threshold,
        config.recency_reliable_neg,
        trend_down_ratio=config.trend_down_ratio,
    )

    # Tag fallback mode in data for downstream awareness
    active_df["_fallback_mode"] = fallback_mode

    # ── Step 7: Sample weighting → final dataset ──────────
    logger.info("═" * 60)
    logger.info("STEP 7: Sample weighting + final dataset")
    active_df = apply_weights_and_smoothing(
        active_df,
        pu_weight_c,
        config.label_smooth_eps_confirmed,
        config.label_smooth_eps_pseudo,
    )

    result = build_final_dataset(active_df, training_history_df, eval_ids, NUMERIC_FEATURES)

    # ── Sanity checks ─────────────────────────────────────
    logger.info("═" * 60)
    logger.info("SANITY CHECKS")
    run_sanity_checks(result, eval_ids)

    # ── Save pipeline artifacts ───────────────────────────
    if output_dir is not None:
        save_pipeline_artifacts(
            result,
            config,
            t_obs,
            w_star,
            prototype,
            output_dir,
        )

    logger.info("═" * 60)
    if fallback_mode:
        logger.warning(
            "Pipeline complete (FALLBACK MODE). Model evaluation will be limited — no ground truth eval set available."
        )
    else:
        logger.info("Pipeline complete. Ready for model training.")

    return result


def save_pipeline_artifacts(
    result: DatasetResult,
    config: DatasetPipelineConfig,
    t_obs: pd.Timestamp,
    w_star: int,
    prototype: dict,
    output_dir: Path,
) -> Path:
    """Save pipeline artifacts for reuse during inference.

    Convention: 13-Data_ML §7.4 — model artifacts with consistent naming.

    Args:
        result: Pipeline output.
        config: Pipeline config used.
        t_obs: Observation date.
        w_star: Selected window size.
        prototype: Leading prototype dict.
        output_dir: Directory to save artifacts.

    Returns:
        Path to the saved artifact file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "scaler": result.scaler,
        "W_star": w_star,
        "prototype": prototype,
        "T_obs": t_obs,
        "feature_names": result.feature_names,
        "config": config.to_safe_dict(),
    }

    output_path = output_dir / "preprocessing_artifacts.pkl"
    with open(output_path, "wb") as f:
        pickle.dump(artifacts, f)

    logger.info("Pipeline artifacts saved to: %s", output_path)
    return output_path
