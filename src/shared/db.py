"""Database connection factories.

Merges duplicated logic from:
  - Ingestion/Data_pull/resources/db.py
  - Preprocess/libs/database.py
  - Modeling/infra/db.py

Conventions applied:
  - 16-Architecture §7.4: Connection pooling.
  - 02-Config §4.3: No os.getenv here — config comes from db_config.
  - 08-Security §7.1: Never log connection strings with credentials.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import psycopg2
from sqlalchemy import create_engine, text

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PgConnection
    from sqlalchemy.engine import Engine

    from config.db_config import PostgresConfig

logger = logging.getLogger(__name__)


def get_engine(
    cfg: PostgresConfig,
    *,
    pool_size: int = 5,
    max_overflow: int = 10,
    echo: bool = False,
) -> Engine:
    """Create a SQLAlchemy engine with connection pooling.

    Args:
        cfg: Database configuration (from config.db_config).
        pool_size: Number of connections to keep in the pool.
        max_overflow: Max connections beyond pool_size.
        echo: If True, log all SQL statements.

    Returns:
        Configured SQLAlchemy Engine instance.
    """
    engine = create_engine(
        cfg.sqlalchemy_url(),
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        echo=echo,
    )
    logger.info(
        "SQLAlchemy engine created: host=%s, db=%s, pool=%d+%d",
        cfg.host,
        cfg.dbname,
        pool_size,
        max_overflow,
    )
    return engine


def get_pg_conn(
    cfg: PostgresConfig,
    *,
    autocommit: bool = False,
) -> PgConnection:
    """Create a raw psycopg2 connection.

    Args:
        cfg: Database configuration.
        autocommit: Whether to enable autocommit mode.

    Returns:
        psycopg2 connection instance.
    """
    conn = psycopg2.connect(cfg.dsn())
    conn.autocommit = autocommit
    logger.debug(
        "psycopg2 connection opened: host=%s, db=%s, autocommit=%s",
        cfg.host,
        cfg.dbname,
        autocommit,
    )
    return conn


def smoke_test(cfg: PostgresConfig) -> bool:
    """Quick DB connectivity check.

    Returns:
        True if connection succeeds, False otherwise.
    """
    try:
        engine = get_engine(cfg, pool_size=1, max_overflow=0)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        engine.dispose()
        logger.info("Database smoke test PASSED: %s", cfg.host)
        return True
    except Exception:
        logger.exception("Database smoke test FAILED: %s", cfg.host)
        return False
