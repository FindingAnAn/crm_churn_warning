"""Churn training and scoring pipeline.

Consumes a time-aware training dataset, trains XGBoost, evaluates,
applies guardrail + accept/reject, scores all active customers,
exports risk table, and logs monitoring metrics.

"""

from __future__ import annotations

import logging
import os
import traceback
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.engine import Engine

from data.preprocessing.training_dataset.pipeline_config import DatasetPipelineConfig
from data.preprocessing.training_dataset.run_dataset_pipeline import (
    run_dataset_pipeline,
)
from modeling.artifacts import load_bundle, save_bundle
from modeling.config.best_config import (
    ensure_best_config_table,
    load_latest_accepted_best_config,
    upsert_best_config,
)
from modeling.config.model_config import ModelConfig
from modeling.evaluation.evaluator import evaluate_model
from modeling.evaluation.guardrail import check_accept_reject, check_guardrail
from modeling.serving.risk_table import ensure_risk_table, insert_predictions
from modeling.serving.scorer import compute_reasons, compute_score_stats, score_all
from modeling.training.trainer import get_feature_importance, train_model
from monitoring.model_quality.drift import (
    compute_feature_drift,
    compute_feature_profile,
    upsert_feature_drift,
)
from monitoring.model_quality.run_log import finish_run, new_run_id, start_run
from monitoring.model_quality.score import upsert_score_drift

logger = logging.getLogger(__name__)


def _monitoring_enabled() -> bool:
    raw = os.getenv("ENABLE_MODEL_QUALITY_MONITORING", "true")
    return raw.lower() in {"1", "true", "yes", "on"}


def _monitoring_schema() -> str:
    return os.getenv("ML_MONITOR_SCHEMA", "ml_monitor")


def _monitoring_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("Invalid %s=%r; using %d", name, os.getenv(name), default)
        return default


def _monitoring_call(label: str, func: Any, *args: Any, **kwargs: Any) -> Any:
    if not _monitoring_enabled():
        return None
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        logger.warning("Model-quality monitoring skipped for %s: %s", label, exc)
        return None


def run_churn_pipeline(
    engine: Engine,
    *,
    pipeline_config: DatasetPipelineConfig | None = None,
    model_config: ModelConfig | None = None,
    bundle_dir: str | Path | None = None,
) -> dict:
    """Run the full churn prediction pipeline.

    Steps:
        1. Build the training dataset
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
        from modeling.config.paths import (
            CHURN_MODEL_DIR,  # Lazy: avoid import at module level when env var may not be set yet
        )

        bundle_dir = CHURN_MODEL_DIR / "bundles" / "latest"
    bundle_dir = Path(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    ensure_best_config_table(engine)
    ensure_risk_table(engine)
    horizon = pipeline_config.horizon_months
    fallback_yymm = int(pd.Timestamp("today").strftime("%y%m"))
    monitor_schema = _monitoring_schema()
    run_id = new_run_id()
    window_end = fallback_yymm
    w_star: int | None = None

    summary: dict = {
        "status": "running",
        "horizon": horizon,
        "run_id": run_id,
    }

    _monitoring_call(
        "run_log.start",
        start_run,
        engine,
        run_id=run_id,
        horizon=horizon,
        risk_threshold_pct=int(model_config.risk_threshold_pct),
        notes="monthly churn pipeline started",
        schema=monitor_schema,
    )

    try:
        # ── Step 1: Dataset Prep ──────────────────────────
        logger.info("=" * 70)
        logger.info("STEP 1/8: Dataset Preparation")
        ds = run_dataset_pipeline(engine, pipeline_config)
        window_end = int(ds.metadata.get("window_end", fallback_yymm))
        raw_w_star = ds.metadata.get("w_star")
        w_star = int(raw_w_star) if raw_w_star is not None else None

        logger.info(
            "Dataset ready: train=%d, eval=%d, predict=%d, features=%d",
            len(ds.x_train),
            len(ds.x_eval),
            len(ds.x_predict),
            len(ds.feature_names),
        )

        # ── Step 2: Train XGBoost ─────────────────────────
        logger.info("=" * 70)
        feature_profile = compute_feature_profile(
            ds.x_train,
            feat_cols=ds.feature_names,
            n_bins=_monitoring_int("ML_MONITOR_FEATURE_BINS", 10),
            max_features=_monitoring_int("ML_MONITOR_MAX_FEATURES", 200),
        )
        baseline_profile = feature_profile
        try:
            _, previous_meta = load_bundle(bundle_dir)
            baseline_profile = (
                previous_meta.get("feature_profile")
                or previous_meta.get("training_profile")
                or feature_profile
            )
        except Exception:
            logger.info("No accepted bundle feature profile found; bootstrapping drift baseline from current train set")

        drift_df = compute_feature_drift(ds.x_predict, baseline_profile)
        feature_drift_rows = _monitoring_call(
            "feature_drift.upsert",
            upsert_feature_drift,
            engine,
            window_end=window_end,
            horizon=horizon,
            best_k=w_star,
            drift_df=drift_df,
            schema=monitor_schema,
        )
        summary["feature_drift_rows"] = feature_drift_rows or 0

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
            _monitoring_call(
                "run_log.finish_guardrail_failed",
                finish_run,
                engine,
                run_id=run_id,
                status="GUARDRAIL_FAILED",
                window_end=window_end,
                cand_best_f1=metrics.get("f05"),
                cand_is_accepted=False,
                accepted=False,
                did_retrain=False,
                did_score=False,
                notes=guardrail_msg,
                schema=monitor_schema,
            )
            return summary

        # ── Step 5: Accept/Reject ─────────────────────────
        logger.info("=" * 70)
        logger.info("STEP 5/8: Accept/Reject decision")

        prev_f05 = None
        try:
            prev_cfg = load_latest_accepted_best_config(engine, horizon=horizon)
            prev_f05 = float(prev_cfg.get("metric_f2_val", 0))
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

        config_record = {
            "as_of_month": window_end,
            "horizon": horizon,
            "best_k": int(w_star or 0),
            "use_static": True,
            "best_threshold": metrics["threshold"],
            "best_spw": 1.0,
            "metric_f2_val": metrics["f05"],  # Legacy column stores the precision-focused F0.5 score.
            "metric_roc_auc_val": metrics["pr_auc"],  # Legacy column stores PR-AUC for this pipeline.
            "val_month": window_end,
            "target_month": None,
            "is_accepted": accepted,
            "accept_rule": rule,
            "prev_accepted_f2": prev_f05,
            "accepted_at": pd.Timestamp.utcnow().isoformat(),
            "notes": f"pipeline; features={len(ds.feature_names)}; window_end={window_end}; w_star={w_star}",
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
                "feature_profile": feature_profile,
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
        threshold = float(metrics["threshold"])
        if not accepted:
            try:
                scoring_model, previous_meta = load_bundle(bundle_dir)
                previous_threshold = (
                    previous_meta.get("metrics", {}).get("threshold")
                    or previous_meta.get("config_record", {}).get("best_threshold")
                )
                if previous_threshold is not None:
                    threshold = float(previous_threshold)
                logger.info("Loaded previous model for scoring")
            except Exception:
                logger.warning("No previous model found — using current")
                scoring_model = model

        top_percentile = max(0.0, min(100.0, 100.0 - float(model_config.risk_threshold_pct)))
        scored_df = score_all(scoring_model, ds, threshold, top_percentile=top_percentile)
        effective_threshold = float(scored_df.attrs.get("effective_threshold", threshold))
        summary["threshold_used"] = effective_threshold
        scored_df = compute_reasons(scored_df, scoring_model, top_n=3)
        score_stats = compute_score_stats(scored_df)
        summary["score_stats"] = score_stats
        _monitoring_call(
            "score_drift.upsert",
            upsert_score_drift,
            engine,
            window_end=window_end,
            horizon=horizon,
            best_k=w_star,
            active_cnt=int(score_stats.get("active_count", len(scored_df))),
            churned_now_cnt=int(scored_df.get("y_label", pd.Series(dtype=int)).fillna(0).astype(int).sum()),
            scores=scored_df["churn_probability"].to_numpy(),
            risk_threshold_pct=int(model_config.risk_threshold_pct),
            risk_cnt=int(score_stats.get("risk_count", 0)),
            schema=monitor_schema,
        )

        # ── Step 8: Export to risk table ──────────────────
        logger.info("=" * 70)
        logger.info("STEP 8/8: Export risk predictions")
        n_inserted = insert_predictions(
            engine,
            scored_df,
            threshold=effective_threshold,
            window_end=window_end,
            w_star=w_star,
            horizon=horizon,
        )
        summary["n_inserted"] = n_inserted
        summary["status"] = "success"
        _monitoring_call(
            "run_log.finish_success",
            finish_run,
            engine,
            run_id=run_id,
            status="SUCCESS",
            window_end=window_end,
            cand_best_f1=metrics.get("f05"),
            cand_is_accepted=accepted,
            accepted=accepted,
            did_retrain=summary.get("did_retrain"),
            did_score=True,
            notes=f"{rule}; inserted={n_inserted}; features={len(ds.feature_names)}",
            schema=monitor_schema,
        )

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
        _monitoring_call(
            "run_log.finish_failed",
            finish_run,
            engine,
            run_id=run_id,
            status="FAILED",
            window_end=window_end,
            accepted=summary.get("accepted"),
            did_retrain=summary.get("did_retrain"),
            did_score=bool(summary.get("n_inserted")),
            notes=summary["error"],
            schema=monitor_schema,
        )
        logger.error(
            "Pipeline failed: %s\n%s",
            exc,
            traceback.format_exc(limit=5),
        )
        raise

    return summary
