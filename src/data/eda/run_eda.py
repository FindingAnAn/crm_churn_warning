"""EDA orchestrator and CLI entry point.

Usage (from Docker / Airflow KubernetesPodOperator):
    python -m data.eda.run_eda

Convention: 01-Structure §6.2 — thin CLI, delegates to application layer.
Convention: 08-Security §3 — credentials from env vars only.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from data.eda.config import EdaConfig
from data.eda.report.baseline import compare_to_baseline, load_baseline, save_baseline
from data.eda.report.builder import EdaReport, build_eda_report, report_to_summary_dict
from data.eda.report.persistence import persist_eda_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("eda_cli")


def run_eda(
    engine: Engine,
    config: EdaConfig,
    *,
    df: pd.DataFrame | None = None,
    target_col: str | None = None,
    dfs_by_month: dict[int, pd.DataFrame] | None = None,
    window_end: int | None = None,
    run_id: str | None = None,
) -> dict:
    """Run the full EDA pipeline.

    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine for persistence.
    config : EdaConfig
        Analysis configuration.
    df : pd.DataFrame | None
        Primary dataset.  When ``None``, loads from database.
    target_col : str | None
        Binary target column for target analysis.
    dfs_by_month : dict[int, pd.DataFrame] | None
        Monthly snapshots for temporal analysis.
    window_end : int | None
        YYMM of the analysed period.
    run_id : str | None
        Unique run ID (auto-generated when None).

    Returns
    -------
    dict
        Summary of the EDA run.
    """
    config.validate()
    if run_id is None:
        run_id = _generate_run_id()

    logger.info("EDA run %s — starting", run_id)

    # Load data from DB if not provided
    if df is None:
        df = _load_feature_data(engine, config, window_end)

    # Build report
    report: EdaReport = build_eda_report(
        df, config, target_col=target_col, dfs_by_month=dfs_by_month,
    )

    # Persist to database
    try:
        n_rows = persist_eda_report(
            engine, report, run_id,
            schema=config.schema, window_end=window_end,
        )
        logger.info("Persisted %d rows to %s schema", n_rows, config.schema)
    except Exception:
        logger.exception("Failed to persist EDA report — continuing")

    # Baseline management
    baseline_comparison = None
    if config.is_baseline_run:
        try:
            save_baseline(engine, report, run_id, schema=config.schema)
            logger.info("Saved baseline snapshot")
        except Exception:
            logger.exception("Failed to save baseline — continuing")
    else:
        try:
            baseline = load_baseline(engine, schema=config.schema)
            if baseline:
                cmp = compare_to_baseline(report, baseline)
                if not cmp.empty:
                    baseline_comparison = cmp.to_dict(orient="records")
                    logger.info(
                        "Compared to baseline: %d stat deltas", len(cmp),
                    )
        except Exception:
            logger.exception("Failed to compare baseline — continuing")

    summary = report_to_summary_dict(report)
    summary["run_id"] = run_id
    summary["status"] = "SUCCESS"
    if baseline_comparison:
        summary["baseline_comparison_count"] = len(baseline_comparison)

    # Visualization
    if config.visualize:
        try:
            from data.eda.visualize.charts import render_all_charts
            from data.eda.visualize.html_report import build_html_report

            logger.info("Generating visualization report...")
            charts = render_all_charts(report)
            ts_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            report_filename = f"eda_report_{ts_str}.html"
            report_path = config.report_dir / report_filename
            build_html_report(charts, report.run_metadata, report_path)
            summary["report_path"] = str(report_path)
            logger.info("Visualization report: %s", report_path)
        except Exception:
            logger.exception("Failed to generate visualization — continuing")

    logger.info("EDA run %s — completed", run_id)
    return summary


def _generate_run_id() -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"eda_{ts}_{short}"


def _load_feature_data(
    engine: Engine,
    config: EdaConfig,
    window_end: int | None,
) -> pd.DataFrame:
    """Load feature data from the latest window table.

    Falls back to ``data_static.cus_lifetime`` when no window table
    is found.
    """
    from sqlalchemy import text

    # Try window table first
    if window_end:
        table = f"data_window.cus_feature_{config.temporal_window_months}m"
        try:
            q = text(f"SELECT * FROM {table} LIMIT 1")
            with engine.connect() as conn:
                conn.execute(q)
            logger.info("Loading from %s", table)
            with engine.connect() as conn:
                df = pd.read_sql(f"SELECT * FROM {table}", conn)
            return df
        except Exception:
            logger.warning("Table %s not found — trying lifetime", table)

    # Fallback to lifetime table
    logger.info("Loading from data_static.cus_lifetime")
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM data_static.cus_lifetime", conn)
    return df


# ── CLI entry point ─────────────────────────────────────


def main() -> int:
    """CLI entry point for EDA module.

    Returns
    -------
    int
        Exit code: 0 on success, 1 on failure.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()

        from config.db_config import PostgresConfig
        from shared.db import get_engine

        logger.info("=" * 70)
        logger.info("EDA Module — Starting")
        logger.info("=" * 70)

        # Database
        db_cfg = PostgresConfig.from_env()
        engine = get_engine(db_cfg)

        # EDA-specific env vars
        window_end_str = os.environ.get("EDA_WINDOW_END")
        window_end = int(window_end_str) if window_end_str else None

        is_baseline = os.environ.get(
            "EDA_IS_BASELINE", "false",
        ).lower() in ("true", "1", "yes")

        target_col = os.environ.get("EDA_TARGET_COL") or None

        is_temporal = os.environ.get(
            "EDA_TEMPORAL", "false",
        ).lower() in ("true", "1", "yes")

        temporal_months = int(
            os.environ.get("EDA_TEMPORAL_MONTHS", "6"),
        )

        config = EdaConfig(
            is_baseline_run=is_baseline,
            temporal_window_months=temporal_months,
            visualize=os.environ.get(
                "EDA_VISUALIZE", "false",
            ).lower() in ("true", "1", "yes"),
            report_dir=Path(os.environ.get(
                "EDA_REPORT_DIR", "reports/eda",
            )),
        )

        # Temporal data loading (optional)
        dfs_by_month = None
        if is_temporal:
            dfs_by_month = _load_temporal_data(
                engine, temporal_months, config,
            )

        summary = run_eda(
            engine, config,
            target_col=target_col,
            dfs_by_month=dfs_by_month,
            window_end=window_end,
        )

        # Log summary as JSON for Airflow parsing
        safe_summary = {
            k: v for k, v in summary.items()
            if isinstance(v, (str, int, float, bool, type(None)))
        }
        logger.info("Summary: %s", json.dumps(safe_summary, default=str))
        logger.info("EDA completed successfully")
        return 0

    except Exception as exc:
        logger.exception("EDA crashed: %s", exc)
        return 1


def _load_temporal_data(
    engine: Engine,
    n_months: int,
    config: EdaConfig,
) -> dict[int, pd.DataFrame]:
    """Load monthly feature snapshots for temporal analysis.

    Discovers available ``data_window.cus_feature_*`` tables and
    loads the most recent *n_months*.
    """
    from sqlalchemy import text

    q = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'data_window'
          AND table_name LIKE 'cus_feature_%'
        ORDER BY table_name DESC
    """)
    with engine.connect() as conn:
        tables = [r[0] for r in conn.execute(q).fetchall()]

    if not tables:
        logger.warning("No window tables found for temporal analysis")
        return {}

    tables = tables[:n_months]
    dfs_by_month: dict[int, pd.DataFrame] = {}

    for tbl in tables:
        # Extract YYMM from table name suffix
        parts = tbl.split("_")
        try:
            yymm = int(parts[-1])
        except (ValueError, IndexError):
            continue
        logger.info("Loading temporal snapshot: data_window.%s", tbl)
        with engine.connect() as conn:
            df = pd.read_sql(f"SELECT * FROM data_window.{tbl}", conn)
        dfs_by_month[yymm] = df

    logger.info("Loaded %d monthly snapshots", len(dfs_by_month))
    return dfs_by_month


if __name__ == "__main__":
    sys.exit(main())
