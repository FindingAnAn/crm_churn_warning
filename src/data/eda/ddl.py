"""DDL for the ``eda_reports`` schema.

Convention: follows the pattern in
``monitoring.model_quality.monitoring.ddl.ensure_monitoring_schema``.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

DEFAULT_SCHEMA = "eda_reports"


def ensure_eda_schema(
    engine: Engine,
    schema: str = DEFAULT_SCHEMA,
) -> None:
    """Create the EDA schema and core tables (Postgres).

    Tables
    ------
    - ``<schema>.eda_run_log``       — one row per EDA execution
    - ``<schema>.feature_stats``     — descriptive + missing + outlier
    - ``<schema>.correlation_pairs`` — high-correlation feature pairs
    - ``<schema>.target_analysis``   — point-biserial + WoE/IV
    - ``<schema>.temporal_drift``    — month-over-month PSI/KS
    - ``<schema>.baseline_snapshot`` — active baseline per feature
    """
    ddl = f"""
    CREATE SCHEMA IF NOT EXISTS {schema};

    CREATE TABLE IF NOT EXISTS {schema}.eda_run_log (
        run_id          TEXT PRIMARY KEY,
        run_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        window_end      INT,
        n_features      INT NOT NULL,
        n_rows          INT NOT NULL,
        has_target       BOOLEAN DEFAULT FALSE,
        has_temporal     BOOLEAN DEFAULT FALSE,
        is_baseline      BOOLEAN DEFAULT FALSE,
        config_json     JSONB,
        summary_json    JSONB,
        status          TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS {schema}.feature_stats (
        run_id              TEXT NOT NULL,
        feature_name        TEXT NOT NULL,
        mean                DOUBLE PRECISION,
        median              DOUBLE PRECISION,
        std                 DOUBLE PRECISION,
        skew                DOUBLE PRECISION,
        kurtosis            DOUBLE PRECISION,
        min_val             DOUBLE PRECISION,
        max_val             DOUBLE PRECISION,
        p5                  DOUBLE PRECISION,
        p25                 DOUBLE PRECISION,
        p50                 DOUBLE PRECISION,
        p75                 DOUBLE PRECISION,
        p95                 DOUBLE PRECISION,
        missing_count       INT,
        missing_pct         DOUBLE PRECISION,
        has_inf             BOOLEAN DEFAULT FALSE,
        iqr_outlier_count   INT,
        iqr_outlier_pct     DOUBLE PRECISION,
        zscore_outlier_count INT,
        zscore_outlier_pct  DOUBLE PRECISION,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (run_id, feature_name)
    );

    CREATE TABLE IF NOT EXISTS {schema}.correlation_pairs (
        run_id      TEXT NOT NULL,
        feature_a   TEXT NOT NULL,
        feature_b   TEXT NOT NULL,
        correlation DOUBLE PRECISION,
        method      TEXT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (run_id, feature_a, feature_b)
    );

    CREATE TABLE IF NOT EXISTS {schema}.target_analysis (
        run_id          TEXT NOT NULL,
        feature_name    TEXT NOT NULL,
        pb_correlation  DOUBLE PRECISION,
        pb_p_value      DOUBLE PRECISION,
        iv              DOUBLE PRECISION,
        iv_strength     TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (run_id, feature_name)
    );

    CREATE TABLE IF NOT EXISTS {schema}.temporal_drift (
        run_id              TEXT NOT NULL,
        reference_month     INT NOT NULL,
        comparison_month    INT NOT NULL,
        feature_name        TEXT NOT NULL,
        psi                 DOUBLE PRECISION,
        ks_stat             DOUBLE PRECISION,
        severity            TEXT,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (run_id, reference_month,
                     comparison_month, feature_name)
    );

    CREATE TABLE IF NOT EXISTS {schema}.baseline_snapshot (
        feature_name    TEXT PRIMARY KEY,
        stats_json      JSONB NOT NULL,
        profile_json    JSONB,
        saved_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        saved_run_id    TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_eda_run_log_run_at
        ON {schema}.eda_run_log (run_at DESC);
    CREATE INDEX IF NOT EXISTS idx_feature_stats_run_id
        ON {schema}.feature_stats (run_id);
    CREATE INDEX IF NOT EXISTS idx_temporal_drift_run_id
        ON {schema}.temporal_drift (run_id);
    """
    with engine.begin() as conn:
        for stmt in ddl.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
