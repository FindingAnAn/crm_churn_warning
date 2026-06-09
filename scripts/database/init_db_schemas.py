"""Bootstrap script — Auto-initialize all required DB schemas and tables.

Run this once (or idempotently) to prepare the database:
    python scripts/database/init_db_schemas.py

Creates:
  - Schema ``cskh`` with tables: confirmed_churners, prototype_cache
  - Schema ``data_static`` with tables: model_best_config, etc.
  - Schema ``data_window`` (empty, populated by feature generation)

"""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv
from sqlalchemy import text

logger = logging.getLogger(__name__)


def init_schemas() -> None:
    """Initialize all required schemas and tables."""
    load_dotenv()

    from core.database import get_engine
    from modeling.config.best_config import ensure_best_config_table
    from modeling.serving.risk_table import ensure_risk_table
    from monitoring.model_quality.ddl import ensure_monitoring_schema
    from settings.database import PostgresConfig

    cfg = PostgresConfig.from_env()
    engine = get_engine(cfg)

    logger.info("Connected to: %s:%s/%s", cfg.host, cfg.port, cfg.dbname)

    ddl_statements = [
        # ── Schema: cskh ─────────────────────────────────
        "CREATE SCHEMA IF NOT EXISTS cskh",
        """CREATE TABLE IF NOT EXISTS cskh.confirmed_churners (
            id              SERIAL PRIMARY KEY,
            cms_code_enc    VARCHAR(100) NOT NULL,
            file_month      INT NOT NULL,
            file_year       INT NOT NULL,
            source_file     VARCHAR(255),
            loaded_at       TIMESTAMP DEFAULT NOW(),
            UNIQUE(cms_code_enc, file_month, file_year)
        )""",
        """CREATE TABLE IF NOT EXISTS cskh.prototype_cache (
            id              SERIAL PRIMARY KEY,
            run_month       INT NOT NULL,
            horizon         INT NOT NULL,
            n_confirmed     INT NOT NULL,
            n_features      INT NOT NULL,
            mu              BYTEA NOT NULL,
            sigma_inv       BYTEA NOT NULL,
            sigma2          DOUBLE PRECISION NOT NULL,
            feature_names   TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT NOW(),
            UNIQUE(run_month, horizon)
        )""",
        # Indexes
        ("CREATE INDEX IF NOT EXISTS idx_confirmed_month_year ON cskh.confirmed_churners(file_month, file_year)"),
        ("CREATE INDEX IF NOT EXISTS idx_prototype_horizon ON cskh.prototype_cache(horizon, run_month DESC)"),
        # ── Schema: data_static ──────────────────────────
        "CREATE SCHEMA IF NOT EXISTS data_static",
        # ── Schema: data_window ──────────────────────────
        "CREATE SCHEMA IF NOT EXISTS data_window",
        # ── Schema: ingest ───────────────────────────────
        "CREATE SCHEMA IF NOT EXISTS ingest",
    ]

    with engine.begin() as conn:
        for stmt in ddl_statements:
            try:
                conn.execute(text(stmt))
                label = stmt.strip()[:70].replace("\n", " ")
                logger.info("OK: %s...", label)
            except Exception as exc:
                logger.error("FAILED: %s... → %s", stmt[:60], exc)
                raise

    ensure_best_config_table(engine)
    ensure_risk_table(engine)
    ensure_monitoring_schema(engine)

    logger.info("═" * 50)
    logger.info("All schemas initialized successfully.")

    # Verify
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name IN ('cskh', 'data_static', 'data_window', 'ingest', 'ml_monitor') "
                "ORDER BY schema_name"
            )
        )
        schemas = [row[0] for row in result]
        logger.info("Verified schemas: %s", schemas)


if __name__ == "__main__":
    try:
        from core.logging import configure_logging_from_env

        configure_logging_from_env(app_name="database_schema_init")
        init_schemas()
    except Exception as exc:
        logger.error("Schema initialization failed: %s", exc)
        sys.exit(1)
