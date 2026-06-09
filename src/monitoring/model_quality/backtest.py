from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .ddl import DEFAULT_SCHEMA, ensure_monitoring_schema


def compute_precision_in_list(
    predictions: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    id_col: str = "cms_code_enc",
    pred_flag_col: str = "churn_flag",
    label_col: str = "churned",
) -> dict:
    """Compute backtest metrics once the future label window is available."""
    if predictions.empty:
        return {
            "active_cnt": 0,
            "list_size": 0,
            "churn_true_total": 0,
            "churn_true_in_list": 0,
            "precision_in_list": None,
            "recall_in_list": None,
            "f1_in_list": None,
        }

    pred_ids = predictions.loc[predictions[pred_flag_col] == 1, id_col].astype(str)
    label_map = labels[[id_col, label_col]].copy()
    label_map[id_col] = label_map[id_col].astype(str)

    joined = pd.DataFrame({id_col: pred_ids}).merge(label_map, on=id_col, how="left")
    true_in_list = int(joined[label_col].fillna(0).astype(int).sum())
    list_size = int(len(pred_ids))
    true_total = int(label_map[label_col].fillna(0).astype(int).sum())
    precision = true_in_list / list_size if list_size else None
    recall = true_in_list / true_total if true_total else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else None
    )

    return {
        "active_cnt": int(len(predictions)),
        "list_size": list_size,
        "churn_true_total": true_total,
        "churn_true_in_list": true_in_list,
        "precision_in_list": precision,
        "recall_in_list": recall,
        "f1_in_list": f1,
    }


def upsert_backtest(
    engine: Engine,
    *,
    pred_window_end: int,
    label_window_end: int,
    horizon: int,
    best_k: int | None,
    risk_threshold_pct: int,
    metrics: dict,
    schema: str = DEFAULT_SCHEMA,
) -> dict:
    """Persist precision-in-list backtest metrics."""
    ensure_monitoring_schema(engine, schema=schema)
    payload = {
        "pred_window_end": int(pred_window_end),
        "label_window_end": int(label_window_end),
        "horizon": int(horizon),
        "best_k": int(best_k) if best_k is not None else None,
        "risk_threshold_pct": int(risk_threshold_pct),
        "active_cnt": int(metrics.get("active_cnt") or 0),
        "list_size": int(metrics.get("list_size") or 0),
        "churn_true_total": int(metrics.get("churn_true_total") or 0),
        "churn_true_in_list": int(metrics.get("churn_true_in_list") or 0),
        "precision_in_list": metrics.get("precision_in_list"),
        "recall_in_list": metrics.get("recall_in_list"),
        "f1_in_list": metrics.get("f1_in_list"),
    }
    q = text(f"""
        INSERT INTO {schema}.backtest (
            pred_window_end, label_window_end, horizon,
            best_k, risk_threshold_pct,
            active_cnt, list_size, churn_true_total, churn_true_in_list,
            precision_in_list, recall_in_list, f1_in_list
        )
        VALUES (
            :pred_window_end, :label_window_end, :horizon,
            :best_k, :risk_threshold_pct,
            :active_cnt, :list_size, :churn_true_total, :churn_true_in_list,
            :precision_in_list, :recall_in_list, :f1_in_list
        )
        ON CONFLICT (pred_window_end, horizon)
        DO UPDATE SET
            label_window_end = EXCLUDED.label_window_end,
            best_k = EXCLUDED.best_k,
            risk_threshold_pct = EXCLUDED.risk_threshold_pct,
            active_cnt = EXCLUDED.active_cnt,
            list_size = EXCLUDED.list_size,
            churn_true_total = EXCLUDED.churn_true_total,
            churn_true_in_list = EXCLUDED.churn_true_in_list,
            precision_in_list = EXCLUDED.precision_in_list,
            recall_in_list = EXCLUDED.recall_in_list,
            f1_in_list = EXCLUDED.f1_in_list,
            created_at = now()
    """)
    with engine.begin() as conn:
        conn.execute(q, payload)
    return payload
