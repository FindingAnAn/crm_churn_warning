"""Monthly pipeline v2 — orchestrator.

Consumes DatasetResult from dataset_prep, trains XGBoost, evaluates,
applies guardrail + accept/reject, scores all active customers,
exports risk table, and logs monitoring metrics.

Convention: 01-Structure §6.2 — application layer orchestrates workflow.
Convention: 13-Data_ML §9.2 — explicit step boundaries.
"""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from data.preprocessing.dataset_prep.pipeline_config import DatasetPipelineConfig
from data.preprocessing.dataset_prep.run_dataset_pipeline import (
    run_dataset_pipeline,
)
from modeling.common.artifacts import load_bundle, save_bundle
from modeling.config.model_config import ModelConfig
from modeling.config_store.best_config import (
    ensure_best_config_table,
    load_latest_accepted_best_config,
    upsert_best_config,
)
from modeling.export.risk_table import ensure_risk_table, insert_predictions
from modeling.export.scorer import compute_reasons, compute_score_stats, score_all
from modeling.train.evaluator import evaluate_model
from modeling.train.guardrail import check_accept_reject, check_guardrail
from modeling.train.trainer import get_feature_importance, train_model

logger = logging.getLogger(__name__)


def run_monthly_v2(
    engine: Engine,
    *,
    pipeline_config: DatasetPipelineConfig | None = None,
    model_config: ModelConfig | None = None,
    bundle_dir: str | Path | None = None,
) -> dict:
    """Run the full monthly churn prediction pipeline (v2).

    Steps:
        1. Run dataset_prep pipeline (7 steps) → DatasetResult
        2. Train XGBoost on DatasetResult
        3. Evaluate on eval set (confirmed churners)
        4. Guardrail check (min F1/PR-AUC)
        5. Accept/Reject decision (F1 vs previous)
        6. Save bundle (if accepted)
        7. Score all active customers
        8. Export to risk table

    Args:
        engine: SQLAlchemy engine.
        pipeline_config: Dataset pipeline config (default = DatasetPipelineConfig()).
        model_config: Model training config (default = ModelConfig()).
        bundle_dir: Path to save/load model bundles.

    Returns:
        Summary dict with all step results.
    """
    if pipeline_config is None:
        pipeline_config = DatasetPipelineConfig()
    if model_config is None:
        model_config = ModelConfig()

    pipeline_config.validate()
    model_config.validate()

    if bundle_dir is None:
        from modeling.config.paths import CHURN_MODEL_DIR  # Lazy: avoid import at module level when env var may not be set yet

        bundle_dir = CHURN_MODEL_DIR / "bundles" / "latest"
    bundle_dir = Path(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    ensure_best_config_table(engine)
    ensure_risk_table(engine)
    horizon = pipeline_config.horizon_months

    summary: dict = {
        "status": "running",
        "horizon": horizon,
    }

    try:
        # ── Step 1: Dataset Prep ──────────────────────────
        logger.info("=" * 70)
        logger.info("STEP 1/8: Dataset Preparation")
        ds = run_dataset_pipeline(engine, pipeline_config)

        logger.info(
            "Dataset ready: train=%d, eval=%d, predict=%d, features=%d",
            len(ds.x_train),
            len(ds.x_eval),
            len(ds.x_predict),
            len(ds.feature_names),
        )

        # ── Step 2: Train XGBoost ─────────────────────────
        logger.info("=" * 70)
        logger.info("STEP 2/8: Train XGBoost")
        model = train_model(ds, model_config)
        feat_importance = get_feature_importance(model)

        # ── Step 3: Evaluate ──────────────────────────────
        logger.info("=" * 70)
        logger.info("STEP 3/8: Evaluate on confirmed set")
        metrics = evaluate_model(model, ds)
        summary["metrics"] = metrics

        # ── Step 4: Guardrail ─────────────────────────────
        logger.info("=" * 70)
        logger.info("STEP 4/8: Guardrail check")
        passed, guardrail_msg = check_guardrail(
            metrics,
            min_f05=model_config.min_f1,  # use legacy config attribute for F0.5
            min_pr_auc=model_config.min_pr_auc,
        )
        summary["guardrail_passed"] = passed
        summary["guardrail_msg"] = guardrail_msg

        if not passed:
            summary["status"] = "guardrail_failed"
            logger.error("Pipeline stopped: %s", guardrail_msg)
            return summary

        # ── Step 5: Accept/Reject ─────────────────────────
        logger.info("=" * 70)
        logger.info("STEP 5/8: Accept/Reject decision")

        prev_f05 = None
        try:
            prev_cfg = load_latest_accepted_best_config(engine, horizon=horizon)
            prev_f05 = float(prev_cfg.get("metric_f1_val", 0))  # read legacy column
        except ValueError:
            logger.info("No previous accepted model found for horizon=%s. Using baseline logic.", horizon)
        except Exception as e:
            logger.warning("Unexpected error loading previous config: %s", e)

        accepted, rule = check_accept_reject(
            metrics["f05"],
            prev_f05,
            eps=model_config.f1_improve_eps,
        )
        summary["accepted"] = accepted
        summary["accept_rule"] = rule

        # Store config (accepted or rejected)

        # as_of_month is stored as YYMM integer (e.g. 2512)
        current_yymm = int(pd.Timestamp("today").strftime("%y%m"))

        config_record = {
            "as_of_month": current_yymm,
            "horizon": horizon,
            "best_k": 0,
            "use_static": True,
            "best_threshold": metrics["threshold"],
            "best_spw": 1.0,
            "metric_f1_val": metrics["f05"],  # Store F0.5 in legacy F1 column
            "metric_pr_auc_val": metrics["pr_auc"],
            "val_month": None,
            "target_month": None,
            "is_accepted": accepted,
            "accept_rule": rule,
            "prev_accepted_f1": prev_f05,
            "accepted_at": pd.Timestamp.utcnow().isoformat(),
            "notes": f"v2 pipeline; features={len(ds.feature_names)}",
        }
        upsert_best_config(engine, config_record)

        # ── Step 6: Save bundle (if accepted) ─────────────
        logger.info("=" * 70)
        logger.info("STEP 6/8: Save model bundle")

        if accepted:
            meta = {
                "config_record": config_record,
                "model_config": model_config.to_safe_dict(),
                "pipeline_config": pipeline_config.to_safe_dict(),
                "metrics": metrics,
                "feature_names": ds.feature_names,
                "feature_importance": feat_importance,
            }
            save_bundle(bundle_dir, model, metadata=meta)
            logger.info("Bundle saved to %s", bundle_dir)
            summary["did_retrain"] = True
        else:
            logger.info("Model NOT accepted — keeping previous bundle")
            summary["did_retrain"] = False

        # ── Step 7: Score all active customers ────────────
        logger.info("=" * 70)
        logger.info("STEP 7/8: Score all active customers")

        scoring_model = model
        if not accepted:
            try:
                scoring_model, _ = load_bundle(bundle_dir)
                logger.info("Loaded previous model for scoring")
            except Exception:
                logger.warning("No previous model found — using current")
                scoring_model = model

        threshold = metrics["threshold"]
        scored_df = score_all(scoring_model, ds, threshold)
        scored_df = compute_reasons(scored_df, scoring_model, top_n=3)
        score_stats = compute_score_stats(scored_df)
        summary["score_stats"] = score_stats

        # ── Step 8: Export to risk table ──────────────────
        logger.info("=" * 70)
        logger.info("STEP 8/8: Export risk predictions")
        n_inserted = insert_predictions(
            engine,
            scored_df,
            threshold=threshold,
            w_star=None,  # Deferred: w_star not yet tracked in v2 pipeline artifacts (non-blocking)
            horizon=horizon,
        )
        summary["n_inserted"] = n_inserted
        summary["status"] = "success"

        logger.info("=" * 70)
        logger.info(
            "PIPELINE COMPLETE: %d active → %d flagged → %d inserted",
            score_stats.get("active_count", 0),
            score_stats.get("risk_count", 0),
            n_inserted,
        )

    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        logger.error(
            "Pipeline failed: %s\n%s",
            exc,
            traceback.format_exc(limit=5),
        )
        raise

    return summary
