"""Ingestion resources/db.py — thin wrapper around centralized config.

This file delegates to config.db_config.PostgresConfig to avoid
duplicating the PostgresConfig dataclass and hardcoded credentials.

Convention: 08-Security §3.2 — no hardcoded credentials.
"""

import psycopg2

# Re-export from centralized config for backward compatibility
from config.db_config import PostgresConfig


def get_pg_conn(cfg: PostgresConfig, *, autocommit: bool = False):
    """Get a psycopg2 connection from PostgresConfig.

    Args:
        cfg: PostgresConfig instance (use ``PostgresConfig.from_env()``).
        autocommit: Enable autocommit mode.

    Returns:
        psycopg2 connection.
    """
    conn = psycopg2.connect(cfg.dsn())
    conn.autocommit = autocommit
    return conn
