"""Prototype cache — save/load leading prototype to/from DB.

Mỗi lần build prototype thành công (có CSKH), lưu vào bảng
``cskh.prototype_cache``. Tháng sau, nếu không có CSKH,
load bản prototype gần nhất.

Conventions applied:
  - 13-Data_ML §9.1: Idempotent DDL (IF NOT EXISTS).
  - 13-Data_ML §7.4: Model artifacts with consistent naming.
  - 08-Security §7.1: No credentials in logs.
"""

from __future__ import annotations

import json
import logging
import pickle
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

CACHE_SCHEMA = "cskh"
CACHE_TABLE = "prototype_cache"


def ensure_prototype_cache_table(engine: Engine) -> None:
    """Create the prototype_cache table if not exists.

    Convention: 13-Data_ML §9.1 — idempotent DDL.
    """
    ddl = [
        "CREATE SCHEMA IF NOT EXISTS cskh",
        f"""CREATE TABLE IF NOT EXISTS {CACHE_SCHEMA}.{CACHE_TABLE} (
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
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))


def save_prototype(
    engine: Engine,
    prototype: dict[str, Any],
    run_month: int,
    horizon: int,
) -> None:
    """Save a prototype to the DB cache.

    Args:
        engine: SQLAlchemy engine.
        prototype: Dict from ``build_leading_prototype`` with keys:
            mu, Sigma_inv, sigma2, feature_names, n_confirmed.
        run_month: Run month in YYMM format (e.g. 2601).
        horizon: Prediction horizon in months.
    """
    if not prototype:
        logger.warning("Empty prototype — not saving to cache")
        return

    ensure_prototype_cache_table(engine)

    mu_bytes = pickle.dumps(prototype["mu"])
    sigma_inv_bytes = pickle.dumps(prototype["Sigma_inv"])
    feature_names_json = json.dumps(prototype["feature_names"])

    upsert_sql = text(f"""
        INSERT INTO {CACHE_SCHEMA}.{CACHE_TABLE}
            (run_month, horizon, n_confirmed, n_features,
             mu, sigma_inv, sigma2, feature_names)
        VALUES
            (:run_month, :horizon, :n_confirmed, :n_features,
             :mu, :sigma_inv, :sigma2, :feature_names)
        ON CONFLICT (run_month, horizon) DO UPDATE SET
            n_confirmed = EXCLUDED.n_confirmed,
            n_features = EXCLUDED.n_features,
            mu = EXCLUDED.mu,
            sigma_inv = EXCLUDED.sigma_inv,
            sigma2 = EXCLUDED.sigma2,
            feature_names = EXCLUDED.feature_names,
            created_at = NOW()
    """)

    with engine.begin() as conn:
        conn.execute(
            upsert_sql,
            {
                "run_month": run_month,
                "horizon": horizon,
                "n_confirmed": prototype["n_confirmed"],
                "n_features": len(prototype["feature_names"]),
                "mu": mu_bytes,
                "sigma_inv": sigma_inv_bytes,
                "sigma2": float(prototype["sigma2"]),
                "feature_names": feature_names_json,
            },
        )

    logger.info(
        "Prototype cached: run_month=%d, horizon=%d, n_confirmed=%d, n_features=%d",
        run_month,
        horizon,
        prototype["n_confirmed"],
        len(prototype["feature_names"]),
    )


def load_latest_prototype(
    engine: Engine,
    horizon: int,
    *,
    max_age_months: int = 3,
    current_month: int | None = None,
) -> dict[str, Any] | None:
    """Load the most recent cached prototype for a given horizon.

    Args:
        engine: SQLAlchemy engine.
        horizon: Prediction horizon in months.
        max_age_months: Maximum age of cached prototype (in months).
            If the cached prototype is older than this, return None.
        current_month: Current month in YYMM format (for age check).
            If None, skip age check.

    Returns:
        Prototype dict with keys: mu, Sigma_inv, sigma2, feature_names,
        n_confirmed, cached_run_month, cached_at.
        None if no cache found or cache too old.
    """
    ensure_prototype_cache_table(engine)

    sql = text(f"""
        SELECT run_month, horizon, n_confirmed, n_features,
               mu, sigma_inv, sigma2, feature_names, created_at
        FROM {CACHE_SCHEMA}.{CACHE_TABLE}
        WHERE horizon = :h
        ORDER BY run_month DESC
        LIMIT 1
    """)

    with engine.connect() as conn:
        result = conn.execute(sql, {"h": horizon})
        row = result.fetchone()

    if row is None:
        logger.warning("No cached prototype found for horizon=%d", horizon)
        return None

    cached_run_month = row[0]

    # Age check
    if current_month is not None and max_age_months > 0:
        age = _months_diff(current_month, cached_run_month)
        if age > max_age_months:
            logger.warning(
                "Cached prototype too old: %d months (max=%d). run_month=%d, current=%d",
                age,
                max_age_months,
                cached_run_month,
                current_month,
            )
            return None

    mu = pickle.loads(row[4])
    sigma_inv = pickle.loads(row[5])
    feature_names = json.loads(row[7])

    prototype = {
        "mu": mu,
        "Sigma_inv": sigma_inv,
        "sigma2": float(row[6]),
        "feature_names": feature_names,
        "n_confirmed": row[2],
        "cached_run_month": cached_run_month,
        "cached_at": row[8],
    }

    logger.info(
        "Loaded cached prototype: run_month=%d, n_confirmed=%d, n_features=%d, cached_at=%s",
        cached_run_month,
        row[2],
        row[3],
        row[8],
    )
    return prototype


def _months_diff(yymm_a: int, yymm_b: int) -> int:
    """Compute month difference between two YYMM integers.

    Returns:
        Number of months (a - b). Can be negative.
    """
    ya, ma = divmod(int(yymm_a), 100)
    yb, mb = divmod(int(yymm_b), 100)
    return (ya - yb) * 12 + (ma - mb)
