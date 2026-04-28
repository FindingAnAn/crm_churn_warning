"""Step 2 — Activity tiering.

Compute recency and assign customers to activity tiers
(active / at_risk / churned) based on configurable thresholds.

Conventions applied:
  - 13-Data_ML §6.2: Isolated, stateless feature functions.
  - 13-Data_ML §9.3: Returns new DataFrame, does not modify input in-place.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def detect_t_obs(
    engine: Engine,
    data_start: pd.Timestamp,
    t_obs_override: pd.Timestamp | None = None,
) -> pd.Timestamp:
    """Detect the observation date (T_obs) from available data.

    If ``t_obs_override`` is set, use it directly.
    Otherwise, auto-detect from the latest ``bccp_orderitem_YYMM`` table.

    Args:
        engine: SQLAlchemy engine instance.
        data_start: Earliest date considered in the pipeline.
        t_obs_override: Manual override date (optional).

    Returns:
        T_obs as a pd.Timestamp (first day of the latest month).
    """
    if t_obs_override is not None:
        logger.info("T_obs override: %s", t_obs_override.date())
        return t_obs_override

    sql = text("""
        SELECT tablename
        FROM pg_catalog.pg_tables
        WHERE schemaname = 'public'
          AND tablename LIKE 'bccp_orderitem_%'
        ORDER BY tablename
    """)

    with engine.connect() as conn:
        tbl_df = pd.read_sql(sql, conn)

    pattern = re.compile(r"bccp_orderitem_(\d{4})$")
    yymm_list = [m.group(1) for t in tbl_df["tablename"] if (m := pattern.match(t))]

    if yymm_list:
        latest = max(yymm_list)
        t_obs = pd.Timestamp(f"20{latest[:2]}-{latest[2:]}-01")
        logger.info(
            "T_obs auto-detected from bccp_orderitem_%s: %s",
            latest,
            t_obs.date(),
        )
        return t_obs

    # Fallback: use cas_customer max report_month
    sql_fallback = text("SELECT MAX(date_trunc('month', report_month))::date AS mx FROM public.cas_customer")
    with engine.connect() as conn:
        result = pd.read_sql(sql_fallback, conn)
    t_obs = pd.Timestamp(result.iloc[0, 0])
    logger.info("T_obs fallback from cas_customer: %s", t_obs.date())
    return t_obs


def compute_recency(
    engine: Engine,
    working_df: pd.DataFrame,
    t_obs: pd.Timestamp,
    data_start: pd.Timestamp,
) -> pd.DataFrame:
    """Compute recency (days since last activity) for each customer.

    Args:
        engine: SQLAlchemy engine.
        working_df: Working set DataFrame (must have ``cms_code_enc``).
        t_obs: Observation date.
        data_start: Pipeline data start date.

    Returns:
        Working set with ``last_active_month`` and ``recency_days`` columns added.
    """
    sql = text("""
        SELECT
            cms_code_enc,
            MAX(report_month) AS last_active_month,
            DATE_PART('day', :t_obs ::timestamp - MAX(report_month))::int
                AS recency_days
        FROM public.cas_customer
        WHERE report_month >= :data_start
        GROUP BY cms_code_enc
    """)

    with engine.connect() as conn:
        recency_df = pd.read_sql(
            sql,
            conn,
            params={
                "t_obs": t_obs.isoformat(),
                "data_start": data_start.isoformat(),
            },
        )

    result = working_df.merge(recency_df, on="cms_code_enc", how="left")
    result["recency_days"] = result["recency_days"].fillna(9999).astype(int)

    logger.info(
        "Recency computed: median=%d days, max=%d days",
        result["recency_days"].median(),
        result["recency_days"].max(),
    )
    return result


def assign_tiers(
    df: pd.DataFrame,
    recency_active: int,
    recency_at_risk: int,
) -> pd.DataFrame:
    """Assign activity tiers based on recency thresholds.

    Tiers:
      - ``active``: recency <= recency_active
      - ``at_risk``: recency_active < recency <= recency_at_risk
      - ``churned``: recency > recency_at_risk

    Args:
        df: DataFrame with ``recency_days`` column.
        recency_active: Upper bound for 'active' tier (days).
        recency_at_risk: Upper bound for 'at_risk' tier (days).

    Returns:
        DataFrame with ``tier`` column added.
    """
    result = df.copy()
    conditions = [
        result["recency_days"] <= recency_active,
        result["recency_days"] <= recency_at_risk,
    ]
    choices = ["active", "at_risk"]
    result["tier"] = np.select(conditions, choices, default="churned")

    tier_counts = result["tier"].value_counts()
    logger.info("Tiers assigned: %s", tier_counts.to_dict())

    return result
