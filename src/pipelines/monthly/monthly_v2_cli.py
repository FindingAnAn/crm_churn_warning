"""CLI entry point for monthly v2 pipeline.

Usage (from Docker / Airflow BashOperator):
    python -m pipelines.monthly.monthly_v2_cli

Convention: 01-Structure §6.2 — thin CLI, delegates to application layer.
Convention: 08-Security §3 — credentials from env vars only.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("monthly_v2_cli")


def main() -> int:
    """Run the monthly churn prediction pipeline v2.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()

        from config.db_config import PostgresConfig
        from data.preprocessing.dataset_prep.pipeline_config import DatasetPipelineConfig
        from pipelines.monthly.monthly_v2 import run_monthly_v2
        from shared.db import get_engine

        logger.info("=" * 70)
        logger.info("Monthly Churn Pipeline v2 — Starting")
        logger.info("=" * 70)

        # ── Load DB config ─────────────────────────────────
        db_cfg = PostgresConfig.from_env()
        engine = get_engine(db_cfg)

        # ── Read pipeline config from env vars ─────────────
        cskh_path = os.environ.get("CSKH_FILE_PATH")
        cskh_dir = os.environ.get("CSKH_DIR")

        if cskh_dir:
            logger.info("CSKH directory: %s", cskh_dir)
        elif cskh_path:
            logger.info("CSKH file: %s", cskh_path)
        else:
            logger.warning("No CSKH_DIR or CSKH_FILE_PATH set — will try DB or fallback")

        pipeline_config = DatasetPipelineConfig(
            cskh_file_path=Path(cskh_path) if cskh_path else None,
            cskh_dir=Path(cskh_dir) if cskh_dir else None,
        )

        bundle_dir = os.environ.get("CHURN_MODEL_DIR")

        summary = run_monthly_v2(
            engine,
            pipeline_config=pipeline_config,
            bundle_dir=Path(bundle_dir) / "bundles" / "latest" if bundle_dir else None,
        )

        logger.info("=" * 70)
        logger.info("Pipeline result: %s", summary.get("status", "unknown"))

        # Log summary as JSON for Airflow log parsing
        safe_summary = {k: v for k, v in summary.items() if isinstance(v, (str, int, float, bool, type(None)))}
        logger.info("Summary: %s", json.dumps(safe_summary, default=str))

        if summary.get("status") == "success":
            logger.info("✓ Pipeline completed successfully")
            return 0
        elif summary.get("status") == "guardrail_failed":
            logger.warning("⚠ Pipeline stopped: guardrail check failed")
            return 0  # Not a crash — guardrail is expected behavior
        else:
            logger.error("✗ Pipeline failed: %s", summary.get("error", "unknown"))
            return 1

    except Exception as exc:
        logger.exception("Pipeline crashed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
