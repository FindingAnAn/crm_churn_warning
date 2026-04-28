"""Baseline snapshot management for EDA.

Save a "healthy" reference state and compare future runs against it.

Convention: follows prototype_cache pattern from
``data.preprocessing.dataset_prep.prototype_cache``.
"""

from __future__ import annotations

import json
import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from data.eda.ddl import DEFAULT_SCHEMA, ensure_eda_schema
from data.eda.report.builder import EdaReport

logger = logging.getLogger(__name__)


def save_baseline(
    engine: Engine,
    report: EdaReport,
    run_id: str,
    *,
    schema: str = DEFAULT_SCHEMA,
) -> int:
    """Persist current descriptive stats as the active baseline.

    Each feature's baseline is upserted (one active baseline per
    feature at any time).

    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine.
    report : EdaReport
        Completed EDA report.
    run_id : str
        Identifier of the run that produced this baseline.
    schema : str
        Target schema.

    Returns
    -------
    int
        Number of features saved.
    """
    ensure_eda_schema(engine, schema=schema)
    desc = report.descriptive_stats
    if desc.empty:
        logger.warning("No descriptive stats — cannot save baseline")
        return 0

    q = text(f"""
        INSERT INTO {schema}.baseline_snapshot
            (feature_name, stats_json, profile_json,
             saved_at, saved_run_id)
        VALUES
            (:feature_name, CAST(:stats_json AS JSONB),
             CAST(:profile_json AS JSONB), now(), :saved_run_id)
        ON CONFLICT (feature_name) DO UPDATE SET
            stats_json = CAST(EXCLUDED.stats_json AS JSONB),
            profile_json = CAST(EXCLUDED.profile_json AS JSONB),
            saved_at = now(),
            saved_run_id = EXCLUDED.saved_run_id
    """)

    payload = []
    for _, row in desc.iterrows():
        stats = {
            k: v for k, v in row.to_dict().items()
            if k != "feature_name" and v is not None and not _is_nan(v)
        }
        payload.append({
            "feature_name": str(row["feature_name"]),
            "stats_json": json.dumps(stats, ensure_ascii=False, default=str),
            "profile_json": None,
            "saved_run_id": run_id,
        })

    with engine.begin() as conn:
        conn.execute(q, payload)

    logger.info("Saved baseline for %d features (run %s)", len(payload), run_id)
    return len(payload)


def load_baseline(
    engine: Engine,
    *,
    schema: str = DEFAULT_SCHEMA,
) -> dict[str, dict] | None:
    """Load the active baseline snapshot.

    Returns
    -------
    dict[str, dict] | None
        Mapping ``feature_name`` -> stats dict, or ``None`` when no
        baseline exists.
    """
    ensure_eda_schema(engine, schema=schema)
    q = text(f"""
        SELECT feature_name, stats_json, profile_json, saved_run_id
        FROM {schema}.baseline_snapshot
        ORDER BY feature_name
    """)
    with engine.connect() as conn:
        rows = conn.execute(q).fetchall()

    if not rows:
        return None

    result: dict[str, dict] = {}
    for r in rows:
        stats = r[1] if isinstance(r[1], dict) else json.loads(r[1] or "{}")
        result[r[0]] = {
            "stats": stats,
            "profile": r[2] if isinstance(r[2], dict) else (
                json.loads(r[2]) if r[2] else None
            ),
            "saved_run_id": r[3],
        }
    return result


def compare_to_baseline(
    report: EdaReport,
    baseline: dict[str, dict],
) -> pd.DataFrame:
    """Compare current descriptive stats against a saved baseline.

    Parameters
    ----------
    report : EdaReport
        Current EDA report.
    baseline : dict[str, dict]
        Output of ``load_baseline()``.

    Returns
    -------
    pd.DataFrame
        Columns: ``feature_name, stat_name, baseline_value,
        current_value, delta, delta_pct``.
    """
    desc = report.descriptive_stats
    if desc.empty or not baseline:
        return pd.DataFrame(
            columns=[
                "feature_name", "stat_name",
                "baseline_value", "current_value",
                "delta", "delta_pct",
            ],
        )

    stat_cols = [
        "mean", "median", "std", "skew", "kurtosis",
        "min_val", "max_val", "p5", "p25", "p50", "p75", "p95",
    ]
    rows: list[dict] = []

    for _, row in desc.iterrows():
        fname = str(row["feature_name"])
        if fname not in baseline:
            continue
        base_stats = baseline[fname].get("stats", {})

        for stat in stat_cols:
            cur = row.get(stat)
            base = base_stats.get(stat)
            if cur is None or base is None:
                continue
            if _is_nan(cur) or _is_nan(base):
                continue

            cur_f = float(cur)
            base_f = float(base)
            delta = cur_f - base_f
            delta_pct = (delta / base_f) if base_f != 0 else None

            rows.append({
                "feature_name": fname,
                "stat_name": stat,
                "baseline_value": round(base_f, 6),
                "current_value": round(cur_f, 6),
                "delta": round(delta, 6),
                "delta_pct": round(delta_pct, 6) if delta_pct is not None else None,
            })

    return pd.DataFrame(rows)


def _is_nan(v: object) -> bool:
    try:
        return pd.isna(v)
    except (TypeError, ValueError):
        return False
