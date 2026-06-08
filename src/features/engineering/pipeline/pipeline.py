"""Orchestration for the full churn feature generation pipeline."""

from __future__ import annotations

import argparse

from src.features.engineering.config.app_config import get_config
from src.features.engineering.paths import get_engineering_logs_dir
from src.features.engineering.paths import get_engineering_sql_dir
from src.features.engineering.logging_config import get_logger
from src.features.engineering.logging_config import setup_logging
from src.features.engineering.aggregation.static_features.static import run_static_aggregate
from src.features.engineering.aggregation.window_features.window import render_and_run_all
from src.features.engineering.pipeline.database import create_pipeline_engine
from src.features.engineering.pipeline.database import validate_source_tables
from src.features.engineering.pipeline.dates import resolve_month_plan
from src.features.engineering.pipeline.schema import count_static_customers
from src.features.engineering.pipeline.schema import reset_pipeline_schemas

logger = get_logger("pipeline_main")

DB_STATIC_SQL = get_engineering_sql_dir() / "data_static" / "lifetime_template.sql"


def run(args: argparse.Namespace) -> None:
    setup_logging()

    logger.info("=" * 60)
    logger.info("FEATURE GENERATION PIPELINE STARTED")
    logger.info("=" * 60)

    engine = None
    try:
        cfg = get_config()

        logger.info("\n[STEP 1] Database Connection")
        logger.info("-" * 60)
        engine = create_pipeline_engine(getattr(args, "database_url", None))

        logger.info("\n[STEP 2] Source Table Validation")
        logger.info("-" * 60)
        validate_source_tables(engine)

        logger.info("\n[STEP 3] Date Range Resolution")
        logger.info("-" * 60)
        start_date, end_date, months, window_sizes = resolve_month_plan(
            engine,
            start_value=getattr(args, "start", None),
            end_value=getattr(args, "end", None),
        )
        logger.info(f"[OK] Date range configured: {len(months)} months ({start_date.date()} to {end_date.date()})")
        logger.info(f"[OK] Window sizes: {window_sizes}")

        logger.info("\n[STEP 4] Schema Setup")
        logger.info("-" * 60)
        reset_pipeline_schemas(engine, DB_STATIC_SQL)

        logger.info("\n[STEP 5] Static Feature Aggregation")
        logger.info("-" * 60)
        run_static_aggregate(engine)
        count = count_static_customers(engine)
        if count == 0:
            logger.warning("[WARN] Static feature table is empty after first run. Retrying static aggregation once...")
            run_static_aggregate(engine)
            count = count_static_customers(engine)
        if count == 0:
            logger.error("[FAILED] Static feature table is empty after retry! Check data_static aggregation.")
            raise ValueError("Static feature table is empty after retry!")
        logger.info("[OK] Static phase completed. Proceeding to window phase...")

        logger.info("\n[STEP 6] Window Feature Aggregation")
        logger.info("-" * 60)
        logger.info(f"Rendering and executing {len(months)} month(s) of feature aggregation...")
        worker_count = max(1, cfg.features.window_max_workers) if cfg.features.parallel_render else 1
        logger.info(f"Window execution mode: {'parallel' if worker_count > 1 else 'sequential'} ({worker_count} worker)")
        month_chunk_size = int(getattr(args, "month_chunk_size", 2) or 2)
        window_group_size = int(getattr(args, "window_group_size", 2) or 2)
        resume_window_step6 = bool(getattr(args, "resume_window_step6", False))
        step6_checkpoint = getattr(
            args,
            "step6_checkpoint",
            str(get_engineering_logs_dir() / "step6_window_checkpoint.json"),
        )
        logger.info(
            f"Step 6 chunking: month_chunk_size={month_chunk_size}, "
            f"window_group_size={window_group_size}, resume={resume_window_step6}"
        )
        logger.info(f"Step 6 checkpoint file: {step6_checkpoint}")
        render_and_run_all(
            engine,
            months,
            window_sizes,
            enable_optimization=cfg.features.enable_window_optimization,
            recompute_last_n=cfg.features.recompute_last_n_windows,
            batch_size=cfg.features.batch_insert_size,
            max_workers=worker_count,
            month_chunk_size=month_chunk_size,
            window_group_size=window_group_size,
            checkpoint_path=step6_checkpoint,
            resume_from_checkpoint=resume_window_step6,
            build_lifetime_asof=cfg.features.build_lifetime_asof,
            lifetime_data_start=cfg.features.static_data_start_date,
            feature_engine=cfg.features.feature_engine,
            spark_db_config={
                "host": cfg.database.host,
                "port": cfg.database.port,
                "dbname": cfg.database.dbname,
                "user": cfg.database.user,
                "password": cfg.database.password,
            },
        )
        logger.info("[OK] Window features aggregation complete")

        logger.info("\n" + "=" * 60)
        logger.info("[OK] FEATURE GENERATION PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info(f"Log file: {(get_engineering_logs_dir() / 'pipeline.log').resolve()}")

    except Exception as exc:
        logger.error("\n" + "=" * 60)
        logger.error("[FAILED] FEATURE GENERATION PIPELINE FAILED")
        logger.error("=" * 60)
        logger.exception(f"Error: {exc}")
        raise
    finally:
        if engine is not None:
            logger.info("\nCleaning up database resources...")
            engine.dispose()
            logger.info("[OK] Database resources released")
