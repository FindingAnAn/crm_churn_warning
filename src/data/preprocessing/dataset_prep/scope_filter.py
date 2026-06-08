"""Step 1 — Scope filter.

Load the working set of customers from ``cus_lifetime`` and optionally
load the CSKH confirmed churn list for the evaluation set.

"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def load_working_set(
    engine: Engine,
    min_lifetime_orders: int,
) -> pd.DataFrame:
    """Load customers qualifying for churn analysis.

    Queries ``data_static.cus_lifetime`` and filters by minimum
    lifetime order count.

    Args:
        engine: SQLAlchemy engine instance.
        min_lifetime_orders: Minimum number of lifetime orders.

    Returns:
        DataFrame with one row per qualifying customer.
    """
    sql = text("""
        SELECT
            cl.cms_code_enc,
            cl.is_corporate,
            cl.contract_classify,
            cl.contract_service,
            cl.custype,
            cl.contract_sig_first,
            cl.tenure,
            cl.contract_mgr_org,
            cl.cus_poscode,
            cl.cus_province,
            cl.lifetime_total_items,
            cl.lifetime_total_revenue,
            cl.lifetime_total_weight,
            cl.lifetime_total_complaint,
            cl.lifetime_avg_revenue_per_item,
            cl.lifetime_avg_weight_per_item,
            cl.lifetime_months_active,
            cl.lifetime_days_active,
            cl.lifetime_pct_delay,
            cl.lifetime_pct_refund,
            cl.lifetime_pct_noaccepted,
            cl.lifetime_pct_lost_order,
            cl.lifetime_pct_complaint,
            cl.lifetime_pct_complaint_per_item,
            cl.lifetime_pct_successful_item,
            cl.lifetime_avg_delayday,
            cl.lifetime_avg_order_score,
            cl.lifetime_avg_satisfaction,
            cl.lifetime_service_types_count,
            cl.lifetime_dominant_service,
            cl.lifetime_pct_international,
            cl.lifetime_pct_intra_province,
            cl.most_common_rec_province,
            cl.most_common_rec_district,
            cl.most_common_rec_commune,
            cl.most_common_region
        FROM data_static.cus_lifetime cl
        WHERE cl.lifetime_total_items >= :min_orders
    """)

    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"min_orders": min_lifetime_orders})

    logger.info(
        "Scope filter: loaded %d customers (min_orders=%d)",
        len(df),
        min_lifetime_orders,
    )
    return df


def load_working_set_as_of(
    engine: Engine,
    min_lifetime_orders: int,
    data_start: pd.Timestamp,
    as_of_month: pd.Timestamp,
) -> pd.DataFrame:
    """Load customers qualifying for churn analysis as of one observation month.

    This function avoids look-ahead leakage from ``data_static.cus_lifetime`` by
    computing scope from source activity only up to ``as_of_month``.
    """
    sql = text("""
        WITH activity AS (
            SELECT
                cms_code_enc,
                SUM(item_count)::bigint AS lifetime_total_items,
                SUM(total_fee)::bigint AS lifetime_total_revenue,
                SUM(weight_kg)::double precision AS lifetime_total_weight,
                SUM(total_complaint)::bigint AS lifetime_total_complaint,
                MIN(report_month) AS first_month,
                COUNT(DISTINCT report_month)::int AS lifetime_months_active
            FROM public.cas_customer
            WHERE report_month >= :data_start
              AND report_month <= :as_of_month
            GROUP BY cms_code_enc
            HAVING SUM(item_count) >= :min_orders
        ),
        info AS (
            SELECT DISTINCT ON (cms_code_enc)
                cms_code_enc,
                COALESCE(contract_classify, 1) AS contract_classify,
                COALESCE(contract_service, 62) AS contract_service,
                COALESCE(custype, 1) AS custype,
                contract_sig_first,
                tenure,
                contract_mgr_org,
                cus_poscode,
                cus_province
            FROM public.cas_info
            ORDER BY cms_code_enc, contract_sig_first DESC NULLS LAST
        )
        SELECT
            a.cms_code_enc,
            (LEFT(a.cms_code_enc, 1) = 'T') AS is_corporate,
            i.contract_classify,
            i.contract_service,
            i.custype,
            COALESCE(i.contract_sig_first, date_trunc('month', a.first_month))::timestamp AS contract_sig_first,
            COALESCE(
                i.tenure,
                (
                    EXTRACT(year FROM age(:as_of_month::timestamp, COALESCE(i.contract_sig_first, a.first_month))) * 12
                    + EXTRACT(month FROM age(:as_of_month::timestamp, COALESCE(i.contract_sig_first, a.first_month)))
                )::int
            ) AS tenure,
            i.contract_mgr_org,
            i.cus_poscode,
            i.cus_province,
            a.lifetime_total_items,
            a.lifetime_total_revenue,
            a.lifetime_total_weight,
            a.lifetime_total_complaint,
            a.lifetime_months_active
        FROM activity a
        LEFT JOIN info i ON i.cms_code_enc = a.cms_code_enc
    """)

    params = {
        "data_start": data_start.strftime("%Y-%m-01"),
        "as_of_month": as_of_month.strftime("%Y-%m-01"),
        "min_orders": min_lifetime_orders,
    }
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params=params)

    logger.info(
        "Scope filter as-of %s: loaded %d customers (min_orders=%d)",
        as_of_month.strftime("%Y-%m"),
        len(df),
        min_lifetime_orders,
    )
    return df


def load_eval_ids(
    cskh_file_path: Path | None,
    working_ids: set[str],
) -> set[str]:
    """Load confirmed churn IDs from CSKH file and intersect with working set.

    Args:
        cskh_file_path: Path to CSKH CSV with ``cms_code_enc`` column.
            If None or file not found, returns empty set.
        working_ids: Set of CMS codes in the working set.

    Returns:
        Set of confirmed churn IDs that are in scope.
    """
    if cskh_file_path is None:
        logger.warning("No CSKH file path configured — eval_ids will be empty")
        return set()

    path = Path(cskh_file_path)
    if not path.exists():
        logger.warning("CSKH file not found: %s — eval_ids will be empty", path)
        return set()

    cskh_df = pd.read_csv(path)

    if "cms_code_enc" not in cskh_df.columns:
        raise ValueError(f"CSKH file {path} must contain 'cms_code_enc' column. Found: {list(cskh_df.columns)}")

    confirmed_ids = set(cskh_df["cms_code_enc"].astype(str).str.strip())
    in_scope = confirmed_ids & working_ids
    out_scope = confirmed_ids - working_ids

    logger.info(
        "CSKH: %d total, %d in scope, %d out of scope",
        len(confirmed_ids),
        len(in_scope),
        len(out_scope),
    )

    if out_scope:
        logger.warning(
            "%d confirmed IDs are outside working set scope — check format",
            len(out_scope),
        )

    return in_scope
