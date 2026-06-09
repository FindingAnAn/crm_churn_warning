"""Build leakage-safe lifetime tables for each feature window."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.engine import Engine

from features.engineering.database_utils import execute_sql


def render_lifetime_asof_sql(
    table_name: str,
    data_start: str,
    as_of_date: str,
) -> tuple[str, str]:
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        cms_code_enc VARCHAR(64) PRIMARY KEY,
        lifetime_asof_date DATE NOT NULL,
        lifetime_total_items BIGINT,
        lifetime_total_revenue BIGINT,
        lifetime_total_weight DOUBLE PRECISION,
        lifetime_total_complaint BIGINT,
        lifetime_avg_revenue_per_item DOUBLE PRECISION,
        lifetime_avg_weight_per_item DOUBLE PRECISION,
        lifetime_months_active INT,
        lifetime_pct_delay DOUBLE PRECISION,
        lifetime_pct_refund DOUBLE PRECISION,
        lifetime_pct_noaccepted DOUBLE PRECISION,
        lifetime_pct_lost_order DOUBLE PRECISION,
        lifetime_pct_complaint DOUBLE PRECISION,
        lifetime_pct_successful_item DOUBLE PRECISION,
        lifetime_avg_delayday DOUBLE PRECISION,
        lifetime_avg_order_score DOUBLE PRECISION,
        lifetime_avg_satisfaction DOUBLE PRECISION,
        lifetime_pct_international DOUBLE PRECISION,
        lifetime_pct_intra_province DOUBLE PRECISION
    );
    """

    insert_sql = f"""
    TRUNCATE TABLE {table_name};

    INSERT INTO {table_name} (
        cms_code_enc,
        lifetime_asof_date,
        lifetime_total_items,
        lifetime_total_revenue,
        lifetime_total_weight,
        lifetime_total_complaint,
        lifetime_avg_revenue_per_item,
        lifetime_avg_weight_per_item,
        lifetime_months_active,
        lifetime_pct_delay,
        lifetime_pct_refund,
        lifetime_pct_noaccepted,
        lifetime_pct_lost_order,
        lifetime_pct_complaint,
        lifetime_pct_successful_item,
        lifetime_avg_delayday,
        lifetime_avg_order_score,
        lifetime_avg_satisfaction,
        lifetime_pct_international,
        lifetime_pct_intra_province
    )
    SELECT
        cms_code_enc,
        DATE '{as_of_date}' AS lifetime_asof_date,
        SUM(item_count)::bigint,
        SUM(total_fee)::bigint,
        SUM(weight_kg)::double precision,
        SUM(total_complaint)::bigint,
        COALESCE(SUM(total_fee)::double precision / NULLIF(SUM(item_count), 0), 0),
        COALESCE(SUM(weight_kg)::double precision / NULLIF(SUM(item_count), 0), 0),
        COUNT(DISTINCT report_month)::int,
        COALESCE(SUM(delay_count)::double precision / NULLIF(SUM(item_count), 0), 0),
        COALESCE(SUM(refunded)::double precision / NULLIF(SUM(item_count), 0), 0),
        COALESCE(SUM(noaccepted)::double precision / NULLIF(SUM(item_count), 0), 0),
        COALESCE(SUM(lost_order)::double precision / NULLIF(SUM(item_count), 0), 0),
        COALESCE(SUM(total_complaint)::double precision / NULLIF(SUM(item_count), 0), 0),
        COALESCE((SUM(item_count)::double precision - SUM(nodone)) / NULLIF(SUM(item_count), 0), 0),
        COALESCE(
            SUM(CASE WHEN delay_count > 0 THEN delay_day ELSE 0 END)::double precision
            / NULLIF(SUM(CASE WHEN delay_count > 0 THEN 1 ELSE 0 END), 0),
            0
        ),
        COALESCE(AVG(order_score), 0)::double precision,
        COALESCE(AVG(satisfaction_score), 0)::double precision,
        COALESCE(SUM(international)::double precision / NULLIF(SUM(item_count), 0), 0),
        COALESCE(SUM(CASE WHEN intra_province = 1 THEN 1 ELSE 0 END)::double precision / NULLIF(SUM(item_count), 0), 0)
    FROM public.cas_customer
    WHERE report_month >= DATE '{data_start}'
      AND report_month <= DATE '{as_of_date}'
    GROUP BY cms_code_enc;
    """

    return create_sql, insert_sql


def render_lifetime_asof_sqls(spec: dict[str, Any], data_start: str) -> tuple[str, str]:
    table_name = _lifetime_table_name(spec)
    return render_lifetime_asof_sql(table_name, data_start, spec["end_date"])


def render_and_run_lifetime_asof(
    engine: Engine,
    specs: Sequence[dict[str, Any]],
    data_start: str,
    logger,
) -> int:
    computed = 0
    for spec in specs:
        table_name = _lifetime_table_name(spec)
        create_sql, insert_sql = render_lifetime_asof_sql(table_name, data_start, spec["end_date"])
        execute_sql(engine, create_sql)
        execute_sql(engine, insert_sql)
        computed += 1
    logger.info("Lifetime-as-of tables complete: %d", computed)
    return computed


def _lifetime_table_name(spec: dict[str, Any]) -> str:
    return f"data_window.cus_lifetime_{spec['window_size']}m_{spec['start_ym']}_{spec['end_ym']}"
