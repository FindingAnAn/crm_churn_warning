"""Step 4 — Label construction.

Build label (y_raw) from customer activity in the horizon period
and construct training data from walk-forward windows.

Conventions applied:
  - 13-Data_ML §6.3: Data leakage prevention — labels from future H months only.
  - 13-Data_ML §9.1: Idempotent — same input → same output.
  - 13-Data_ML §9.2: Clear input/output boundaries.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import pandas as pd
from sqlalchemy import text

from data.preprocessing.dataset_prep.ewma import compute_ewma

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Regex to validate feature table names — prevents SQL injection
# Format: data_window.cus_feature_{K}m_{YYMM}_{YYMM}
_TABLE_NAME_PATTERN = re.compile(r"^data_window\.cus_feature_\d+m_\d{4}_\d{4}$")


def get_window_table_name(window_size: int, end_month: pd.Timestamp) -> str:
    """Generate the feature window table name.

    Args:
        window_size: Window size W.
        end_month: End month of the window.

    Returns:
        Fully qualified table name in ``data_window`` schema.
    """
    start_month = end_month - pd.DateOffset(months=window_size - 1)
    return f"data_window.cus_feature_{window_size}m_{start_month.strftime('%y%m')}_{end_month.strftime('%y%m')}"


def load_window_features(
    engine: Engine,
    window_size: int,
    end_month: pd.Timestamp,
) -> pd.DataFrame:
    """Load one feature window table from the database.

    Args:
        engine: SQLAlchemy engine.
        window_size: Window size W.
        end_month: End month of the window.

    Returns:
        Feature DataFrame. Empty DataFrame if table doesn't exist.
    """
    table_name = get_window_table_name(window_size, end_month)

    # Validate table name format to prevent SQL injection
    if not _TABLE_NAME_PATTERN.match(table_name):
        raise ValueError(
            f"Invalid table name format: {table_name}. Expected: data_window.cus_feature_{{K}}m_{{YYMM}}_{{YYMM}}"
        )

    try:
        with engine.connect() as conn:
            df = pd.read_sql(f"SELECT * FROM {table_name}", conn)

        df["_window_table"] = table_name
        df["_W"] = window_size
        df["_end_month"] = end_month

        logger.info(
            "Loaded %s: %d rows, %d cols",
            table_name,
            len(df),
            df.shape[1],
        )
        return df

    except Exception as exc:
        logger.warning("Table %s not found: %s", table_name, exc)
        return pd.DataFrame()


def build_label(
    engine: Engine,
    feature_end: pd.Timestamp,
    horizon_months: int,
) -> pd.DataFrame:
    """Compute label (churn indicator) from customer activity in the horizon.

    y=1 if customer has NEITHER items NOR revenue in
    [feature_end + 1 month, feature_end + H months].

    Args:
        engine: SQLAlchemy engine.
        feature_end: End of the feature window.
        horizon_months: Number of months in the prediction horizon.

    Returns:
        DataFrame with ``cms_code_enc``, ``item_in_horizon``,
        ``rev_in_horizon`` columns.
    """
    label_start = feature_end + pd.DateOffset(months=1)
    label_end = feature_end + pd.DateOffset(months=horizon_months)

    sql = text("""
        SELECT
            cms_code_enc,
            SUM(item_count) AS item_in_horizon,
            SUM(total_fee)  AS rev_in_horizon
        FROM public.cas_customer
        WHERE report_month >= :label_start
          AND report_month <= :label_end
          AND (item_count > 0 OR total_fee > 0)
        GROUP BY cms_code_enc
    """)

    with engine.connect() as conn:
        label_df = pd.read_sql(
            sql,
            conn,
            params={
                "label_start": label_start.strftime("%Y-%m-01"),
                "label_end": label_end.strftime("%Y-%m-01"),
            },
        )

    return label_df


def build_training_windows(
    engine: Engine,
    window_size: int,
    all_months: pd.DatetimeIndex,
    horizon_months: int,
    alpha_ewma: float,
    min_orders_in_w: int = 1,
) -> pd.DataFrame:
    """Build training rows for all windows of a given W.

    For each valid training window, loads features, computes EWMA,
    and constructs the label from the horizon period.

    Args:
        engine: SQLAlchemy engine.
        window_size: Window size W.
        all_months: All available months (DatetimeIndex).
        horizon_months: Prediction horizon H.
        alpha_ewma: EWMA smoothing parameter.
        min_orders_in_w: Minimum orders in window to include a customer.

    Returns:
        Concatenated training DataFrame with features + ``y_raw``.
    """
    # Training window ends: skip H months at the end (no label) + 1 (T_obs)
    train_ends = all_months[window_size - 1 : -(horizon_months + 1)]
    logger.info("W=%d: %d training windows available", window_size, len(train_ends))

    all_rows: list[pd.DataFrame] = []

    for end_month in train_ends:
        feat_df = load_window_features(engine, window_size, end_month)
        if feat_df.empty:
            continue

        # Filter by minimum orders in window
        if "item_sum" in feat_df.columns:
            feat_df = feat_df[feat_df["item_sum"] >= min_orders_in_w]

        # Compute EWMA features
        feat_df = compute_ewma(feat_df, window_size, alpha_ewma)

        # Build labels (y=1 if no items AND no revenue in horizon)
        label_df = build_label(engine, end_month, horizon_months)
        feat_df = feat_df.merge(
            label_df[["cms_code_enc", "item_in_horizon", "rev_in_horizon"]],
            on="cms_code_enc",
            how="left",
        )
        feat_df["item_in_horizon"] = feat_df["item_in_horizon"].fillna(0)
        feat_df["rev_in_horizon"] = feat_df["rev_in_horizon"].fillna(0)
        feat_df["y_raw"] = ((feat_df["item_in_horizon"] == 0) & (feat_df["rev_in_horizon"] == 0)).astype(int)

        all_rows.append(feat_df)

    if not all_rows:
        logger.warning("No training rows produced for W=%d", window_size)
        return pd.DataFrame()

    result = pd.concat(all_rows, ignore_index=True)
    churn_rate = result["y_raw"].mean()
    logger.info(
        "W=%d training data: %d rows, churn_rate=%.2f%%",
        window_size,
        len(result),
        churn_rate * 100,
    )
    return result
