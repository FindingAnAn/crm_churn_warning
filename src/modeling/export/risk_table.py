"""Risk table DDL and insert logic.

Convention: 13-Data_ML §9.1 — idempotent DDL (IF NOT EXISTS).
Convention: 08-Security §3 — no hardcoded credentials.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

RISK_SCHEMA = "data_static"
RISK_TABLE = "churn_risk_predictions"


def ensure_risk_table(engine: Engine) -> str:
    """Create risk table if it does not exist.

    Returns:
        Fully qualified table name.
    """
    ddl = text(f"""
        CREATE TABLE IF NOT EXISTS {RISK_SCHEMA}.{RISK_TABLE} (
            id              SERIAL PRIMARY KEY,
            cms_code_enc    VARCHAR(100) NOT NULL,
            churn_probability FLOAT NOT NULL,
            churn_flag      INT NOT NULL DEFAULT 0,
            threshold_used  FLOAT,
            reason_1        TEXT,
            reason_2        TEXT,
            reason_3        TEXT,
            scored_at       TIMESTAMP DEFAULT NOW(),
            window_end      INT,
            w_star          INT,
            horizon         INT
        );
    """)
    with engine.begin() as conn:
        conn.execute(ddl)

    fqn = f"{RISK_SCHEMA}.{RISK_TABLE}"
    logger.info("Risk table ensured: %s", fqn)
    return fqn


def insert_predictions(
    engine: Engine,
    scored_df: pd.DataFrame,
    *,
    threshold: float,
    window_end: int | None = None,
    w_star: int | None = None,
    horizon: int | None = None,
    clear_previous: bool = True,
) -> int:
    """Insert flagged customers into the risk table.

    Args:
        engine: SQLAlchemy engine.
        scored_df: DataFrame with churn_probability, churn_flag, reason_*.
        threshold: Threshold used for classification.
        window_end: Feature window end month (YYMM).
        w_star: Window size W* from dataset_prep.
        horizon: Prediction horizon in months.
        clear_previous: If True, delete previous entries for this window_end.

    Returns:
        Number of rows inserted.
    """
    flagged = scored_df[scored_df.get("churn_flag", 0) == 1].copy()
    if flagged.empty:
        logger.warning("No customers flagged — nothing to insert")
        return 0

    fqn = f"{RISK_SCHEMA}.{RISK_TABLE}"

    with engine.begin() as conn:
        if clear_previous:
            # Business Rule: Truncate the entire table so every run yields a fresh 10% list
            conn.execute(text(f"TRUNCATE TABLE {fqn}"))
            logger.info("TRUNCATED previous predictions from %s", fqn)

        rows = []
        for _, row in flagged.iterrows():
            rows.append(
                {
                    "cms_code_enc": str(row.get("cms_code_enc", "")),
                    "churn_probability": float(row["churn_probability"]),
                    "churn_flag": 1,
                    "threshold_used": float(threshold),
                    "reason_1": row.get("reason_1"),
                    "reason_2": row.get("reason_2"),
                    "reason_3": row.get("reason_3"),
                    "window_end": window_end,
                    "w_star": w_star,
                    "horizon": horizon,
                }
            )

        if rows:
            insert_sql = text(f"""
                INSERT INTO {fqn}
                    (cms_code_enc, churn_probability, churn_flag,
                     threshold_used, reason_1, reason_2, reason_3,
                     window_end, w_star, horizon)
                VALUES
                    (:cms_code_enc, :churn_probability, :churn_flag,
                     :threshold_used, :reason_1, :reason_2, :reason_3,
                     :window_end, :w_star, :horizon)
            """)
            conn.execute(insert_sql, rows)

    logger.info("Inserted %d risk predictions into %s", len(rows), fqn)
    return len(rows)
