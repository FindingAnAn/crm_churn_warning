"""EDA report assembly — orchestrate all analysis functions.

Convention: 10-Code_design §2.1 — one coherent responsibility.
Convention: 04-Typing §2.1 — typed dataclass for output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from data.eda.config import EdaConfig
from data.eda.stats.correlation import (
    compute_correlation_matrix,
    extract_high_correlations,
)
from data.eda.stats.descriptive import compute_descriptive_stats
from data.eda.stats.missing import compute_missing_pattern, compute_missing_stats
from data.eda.stats.outliers import compute_outlier_stats
from data.eda.target.class_balance import compute_class_distribution
from data.eda.target.feature_target import compute_all_woe_iv, compute_point_biserial
from data.eda.temporal.monthly_drift import compute_monthly_drift
from data.eda.temporal.trend import compute_feature_trends

logger = logging.getLogger(__name__)


@dataclass
class EdaReport:
    """Container for all EDA analysis results.

    Fields are ``None`` when the corresponding analysis was skipped.
    """

    # Requirement A — feature statistics
    descriptive_stats: pd.DataFrame = field(default_factory=pd.DataFrame)
    missing_stats: pd.DataFrame = field(default_factory=pd.DataFrame)
    missing_patterns: list[dict] = field(default_factory=list)
    outlier_stats: pd.DataFrame = field(default_factory=pd.DataFrame)
    correlation_matrix: pd.DataFrame = field(default_factory=pd.DataFrame)
    high_correlations: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Requirement B — target analysis (None when no target)
    class_distribution: dict | None = None
    point_biserial: pd.DataFrame | None = None
    woe_iv: pd.DataFrame | None = None

    # Requirement C — temporal analysis (None when no monthly data)
    monthly_drift: pd.DataFrame | None = None
    feature_trends: pd.DataFrame | None = None

    # Metadata
    run_metadata: dict = field(default_factory=dict)


def build_eda_report(
    df: pd.DataFrame,
    config: EdaConfig,
    *,
    target_col: str | None = None,
    dfs_by_month: dict[int, pd.DataFrame] | None = None,
) -> EdaReport:
    """Orchestrate all EDA analyses into a single report.

    Parameters
    ----------
    df : pd.DataFrame
        Primary dataset to analyse.
    config : EdaConfig
        Analysis configuration.
    target_col : str | None
        Binary target column for requirement B (skip when None).
    dfs_by_month : dict[int, pd.DataFrame] | None
        Monthly snapshots for requirement C (skip when None).

    Returns
    -------
    EdaReport
    """
    feats = config.feature_cols
    logger.info(
        "Building EDA report: %d features, %d rows", len(feats), len(df),
    )

    # ── Requirement A: Feature statistics ──────────────
    logger.info("Computing descriptive stats ...")
    desc = compute_descriptive_stats(df, feats, config.percentiles)

    logger.info("Computing missing-value stats ...")
    miss = compute_missing_stats(df, feats)
    miss_pat = compute_missing_pattern(df, feats)

    logger.info("Computing outlier stats ...")
    out = compute_outlier_stats(
        df, feats, config.outlier_iqr_factor, config.outlier_zscore_threshold,
    )

    logger.info("Computing correlation matrix ...")
    corr = compute_correlation_matrix(df, feats, config.correlation_method)
    high_corr = extract_high_correlations(corr, config.correlation_threshold)

    # ── Requirement B: Target analysis ─────────────────
    cls_dist = None
    pb = None
    woe = None
    if target_col and target_col in df.columns:
        logger.info("Computing target analysis (target=%s) ...", target_col)
        cls_dist = compute_class_distribution(df[target_col])
        pb = compute_point_biserial(df, feats, target_col)
        woe = compute_all_woe_iv(
            df, feats, target_col, config.n_bins, config.woe_min_pct,
        )
    else:
        logger.info("No target column — skipping target analysis")

    # ── Requirement C: Temporal analysis ───────────────
    drift = None
    trends = None
    if dfs_by_month and len(dfs_by_month) >= 2:
        logger.info(
            "Computing temporal analysis (%d months) ...",
            len(dfs_by_month),
        )
        drift = compute_monthly_drift(dfs_by_month, feats, config.n_bins)
        trends = compute_feature_trends(dfs_by_month, feats)
    else:
        logger.info("No monthly data — skipping temporal analysis")

    # ── Metadata ──────────────────────────────────────
    meta = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "n_features": len(feats),
        "n_rows": len(df),
        "has_target": target_col is not None,
        "has_temporal": dfs_by_month is not None and len(dfs_by_month) >= 2,
        "config": config.to_safe_dict(),
    }

    return EdaReport(
        descriptive_stats=desc,
        missing_stats=miss,
        missing_patterns=miss_pat,
        outlier_stats=out,
        correlation_matrix=corr,
        high_correlations=high_corr,
        class_distribution=cls_dist,
        point_biserial=pb,
        woe_iv=woe,
        monthly_drift=drift,
        feature_trends=trends,
        run_metadata=meta,
    )


def report_to_summary_dict(report: EdaReport) -> dict:
    """Flatten an *EdaReport* into a JSON-serializable summary.

    Returns
    -------
    dict
        Top-level keys mirror the report fields; DataFrames are
        converted to row-count summaries.
    """
    summary: dict = {**report.run_metadata}

    # Stats summary
    if not report.descriptive_stats.empty:
        summary["n_features_analysed"] = len(report.descriptive_stats)
    if not report.missing_stats.empty:
        high_miss = report.missing_stats[
            report.missing_stats["missing_pct"] > 0.10
        ]
        summary["features_with_high_missing"] = len(high_miss)
    if not report.outlier_stats.empty:
        high_out = report.outlier_stats[
            report.outlier_stats["iqr_outlier_pct"] > 0.05
        ]
        summary["features_with_high_outliers"] = len(high_out)
    if not report.high_correlations.empty:
        summary["high_correlation_pairs"] = len(report.high_correlations)

    # Target summary
    if report.class_distribution:
        summary["churn_rate"] = report.class_distribution.get("churn_rate")
    if report.woe_iv is not None and not report.woe_iv.empty:
        strong = report.woe_iv[
            report.woe_iv["iv_strength"].isin(["medium", "strong"])
        ]
        summary["strong_iv_features"] = len(strong)

    # Temporal summary
    if report.monthly_drift is not None and not report.monthly_drift.empty:
        alerts = report.monthly_drift[
            report.monthly_drift["severity"] == "ALERT"
        ]
        summary["drift_alert_count"] = len(alerts)
    if report.feature_trends is not None and not report.feature_trends.empty:
        trending = report.feature_trends[
            report.feature_trends["is_trending"] == True  # noqa: E712
        ]
        summary["trending_features"] = len(trending)

    return summary
