"""Persist EDA report to PostgreSQL.

Convention: follows upsert pattern from
``monitoring.model_quality.monitoring.drift.upsert_feature_drift``.
"""

from __future__ import annotations

import json
import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from data.eda.ddl import DEFAULT_SCHEMA, ensure_eda_schema
from data.eda.report.builder import EdaReport, report_to_summary_dict

logger = logging.getLogger(__name__)


def persist_eda_report(
    engine: Engine,
    report: EdaReport,
    run_id: str,
    *,
    schema: str = DEFAULT_SCHEMA,
    window_end: int | None = None,
) -> int:
    """Upsert an EDA report into PostgreSQL.

    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine.
    report : EdaReport
        Completed EDA report.
    run_id : str
        Unique run identifier.
    schema : str
        Target schema.
    window_end : int | None
        YYMM of the analysed period.

    Returns
    -------
    int
        Total rows written across all tables.
    """
    ensure_eda_schema(engine, schema=schema)
    total = 0

    # 1) Run log
    total += _insert_run_log(engine, report, run_id, schema, window_end)

    # 2) Feature stats (merged descriptive + missing + outlier)
    total += _upsert_feature_stats(engine, report, run_id, schema)

    # 3) Correlation pairs
    total += _upsert_correlation_pairs(engine, report, run_id, schema)

    # 4) Target analysis
    total += _upsert_target_analysis(engine, report, run_id, schema)

    # 5) Temporal drift
    total += _upsert_temporal_drift(engine, report, run_id, schema)

    logger.info("Persisted EDA report %s: %d total rows", run_id, total)
    return total


# ── Private helpers ──────────────────────────────────────


def _insert_run_log(
    engine: Engine,
    report: EdaReport,
    run_id: str,
    schema: str,
    window_end: int | None,
) -> int:
    meta = report.run_metadata
    summary = report_to_summary_dict(report)
    q = text(f"""
        INSERT INTO {schema}.eda_run_log
            (run_id, window_end, n_features, n_rows,
             has_target, has_temporal, is_baseline,
             config_json, summary_json, status)
        VALUES
            (:run_id, :window_end, :n_features, :n_rows,
             :has_target, :has_temporal, :is_baseline,
             CAST(:config_json AS JSONB),
             CAST(:summary_json AS JSONB), :status)
        ON CONFLICT (run_id) DO UPDATE SET
            summary_json = CAST(EXCLUDED.summary_json AS JSONB),
            status = EXCLUDED.status
    """)
    params = {
        "run_id": run_id,
        "window_end": window_end,
        "n_features": meta.get("n_features", 0),
        "n_rows": meta.get("n_rows", 0),
        "has_target": meta.get("has_target", False),
        "has_temporal": meta.get("has_temporal", False),
        "is_baseline": meta.get("config", {}).get("is_baseline_run", False),
        "config_json": json.dumps(
            meta.get("config", {}), ensure_ascii=False,
        ),
        "summary_json": json.dumps(summary, ensure_ascii=False, default=str),
        "status": "SUCCESS",
    }
    with engine.begin() as conn:
        conn.execute(q, params)
    return 1


def _upsert_feature_stats(
    engine: Engine,
    report: EdaReport,
    run_id: str,
    schema: str,
) -> int:
    desc = report.descriptive_stats
    miss = report.missing_stats
    out = report.outlier_stats

    if desc.empty:
        return 0

    # Merge all three on feature_name
    merged = desc.copy()
    if not miss.empty:
        merged = merged.merge(
            miss[["feature_name", "missing_count", "missing_pct", "has_inf"]],
            on="feature_name", how="left",
        )
    if not out.empty:
        merged = merged.merge(
            out[[
                "feature_name", "iqr_outlier_count", "iqr_outlier_pct",
                "zscore_outlier_count", "zscore_outlier_pct",
            ]],
            on="feature_name", how="left",
        )

    q = text(f"""
        INSERT INTO {schema}.feature_stats
            (run_id, feature_name, mean, median, std, skew, kurtosis,
             min_val, max_val, p5, p25, p50, p75, p95,
             missing_count, missing_pct, has_inf,
             iqr_outlier_count, iqr_outlier_pct,
             zscore_outlier_count, zscore_outlier_pct)
        VALUES
            (:run_id, :feature_name, :mean, :median, :std, :skew,
             :kurtosis, :min_val, :max_val, :p5, :p25, :p50, :p75,
             :p95, :missing_count, :missing_pct, :has_inf,
             :iqr_outlier_count, :iqr_outlier_pct,
             :zscore_outlier_count, :zscore_outlier_pct)
        ON CONFLICT (run_id, feature_name) DO UPDATE SET
            mean = EXCLUDED.mean, median = EXCLUDED.median,
            std = EXCLUDED.std, skew = EXCLUDED.skew,
            kurtosis = EXCLUDED.kurtosis,
            min_val = EXCLUDED.min_val, max_val = EXCLUDED.max_val,
            p5 = EXCLUDED.p5, p25 = EXCLUDED.p25, p50 = EXCLUDED.p50,
            p75 = EXCLUDED.p75, p95 = EXCLUDED.p95,
            missing_count = EXCLUDED.missing_count,
            missing_pct = EXCLUDED.missing_pct,
            has_inf = EXCLUDED.has_inf,
            iqr_outlier_count = EXCLUDED.iqr_outlier_count,
            iqr_outlier_pct = EXCLUDED.iqr_outlier_pct,
            zscore_outlier_count = EXCLUDED.zscore_outlier_count,
            zscore_outlier_pct = EXCLUDED.zscore_outlier_pct,
            created_at = now()
    """)
    payload = []
    for _, r in merged.iterrows():
        payload.append({
            "run_id": run_id,
            "feature_name": str(r.get("feature_name")),
            "mean": _safe_float(r.get("mean")),
            "median": _safe_float(r.get("median")),
            "std": _safe_float(r.get("std")),
            "skew": _safe_float(r.get("skew")),
            "kurtosis": _safe_float(r.get("kurtosis")),
            "min_val": _safe_float(r.get("min_val")),
            "max_val": _safe_float(r.get("max_val")),
            "p5": _safe_float(r.get("p5")),
            "p25": _safe_float(r.get("p25")),
            "p50": _safe_float(r.get("p50")),
            "p75": _safe_float(r.get("p75")),
            "p95": _safe_float(r.get("p95")),
            "missing_count": _safe_int(r.get("missing_count")),
            "missing_pct": _safe_float(r.get("missing_pct")),
            "has_inf": bool(r.get("has_inf", False)),
            "iqr_outlier_count": _safe_int(r.get("iqr_outlier_count")),
            "iqr_outlier_pct": _safe_float(r.get("iqr_outlier_pct")),
            "zscore_outlier_count": _safe_int(
                r.get("zscore_outlier_count"),
            ),
            "zscore_outlier_pct": _safe_float(
                r.get("zscore_outlier_pct"),
            ),
        })

    with engine.begin() as conn:
        conn.execute(q, payload)
    return len(payload)


def _upsert_correlation_pairs(
    engine: Engine,
    report: EdaReport,
    run_id: str,
    schema: str,
) -> int:
    hc = report.high_correlations
    if hc.empty:
        return 0

    q = text(f"""
        INSERT INTO {schema}.correlation_pairs
            (run_id, feature_a, feature_b, correlation, method)
        VALUES
            (:run_id, :feature_a, :feature_b, :correlation, :method)
        ON CONFLICT (run_id, feature_a, feature_b) DO UPDATE SET
            correlation = EXCLUDED.correlation,
            method = EXCLUDED.method,
            created_at = now()
    """)
    method = report.run_metadata.get("config", {}).get(
        "correlation_method", "pearson",
    )
    payload = [
        {
            "run_id": run_id,
            "feature_a": str(r["feature_a"]),
            "feature_b": str(r["feature_b"]),
            "correlation": _safe_float(r["correlation"]),
            "method": method,
        }
        for _, r in hc.iterrows()
    ]

    with engine.begin() as conn:
        conn.execute(q, payload)
    return len(payload)


def _upsert_target_analysis(
    engine: Engine,
    report: EdaReport,
    run_id: str,
    schema: str,
) -> int:
    pb = report.point_biserial
    woe = report.woe_iv

    if pb is None or pb.empty:
        return 0

    # Merge point-biserial and WoE/IV
    merged = pb.copy()
    if woe is not None and not woe.empty:
        merged = merged.merge(
            woe[["feature_name", "iv", "iv_strength"]],
            on="feature_name", how="left",
        )

    q = text(f"""
        INSERT INTO {schema}.target_analysis
            (run_id, feature_name, pb_correlation, pb_p_value,
             iv, iv_strength)
        VALUES
            (:run_id, :feature_name, :pb_correlation, :pb_p_value,
             :iv, :iv_strength)
        ON CONFLICT (run_id, feature_name) DO UPDATE SET
            pb_correlation = EXCLUDED.pb_correlation,
            pb_p_value = EXCLUDED.pb_p_value,
            iv = EXCLUDED.iv,
            iv_strength = EXCLUDED.iv_strength,
            created_at = now()
    """)
    payload = [
        {
            "run_id": run_id,
            "feature_name": str(r["feature_name"]),
            "pb_correlation": _safe_float(r.get("correlation")),
            "pb_p_value": _safe_float(r.get("p_value")),
            "iv": _safe_float(r.get("iv")),
            "iv_strength": str(r.get("iv_strength"))
            if pd.notna(r.get("iv_strength"))
            else None,
        }
        for _, r in merged.iterrows()
    ]

    with engine.begin() as conn:
        conn.execute(q, payload)
    return len(payload)


def _upsert_temporal_drift(
    engine: Engine,
    report: EdaReport,
    run_id: str,
    schema: str,
) -> int:
    drift = report.monthly_drift
    if drift is None or drift.empty:
        return 0

    q = text(f"""
        INSERT INTO {schema}.temporal_drift
            (run_id, reference_month, comparison_month,
             feature_name, psi, ks_stat, severity)
        VALUES
            (:run_id, :reference_month, :comparison_month,
             :feature_name, :psi, :ks_stat, :severity)
        ON CONFLICT (run_id, reference_month,
                     comparison_month, feature_name)
        DO UPDATE SET
            psi = EXCLUDED.psi,
            ks_stat = EXCLUDED.ks_stat,
            severity = EXCLUDED.severity,
            created_at = now()
    """)
    payload = [
        {
            "run_id": run_id,
            "reference_month": int(r["reference_month"]),
            "comparison_month": int(r["comparison_month"]),
            "feature_name": str(r["feature_name"]),
            "psi": _safe_float(r.get("psi")),
            "ks_stat": _safe_float(r.get("ks_stat")),
            "severity": str(r.get("severity")) if r.get("severity") else None,
        }
        for _, r in drift.iterrows()
    ]

    with engine.begin() as conn:
        conn.execute(q, payload)
    return len(payload)


# ── Type-safe converters ────────────────────────────────


def _safe_float(v: object) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: object) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
