"""EDA chart generators using matplotlib.

Each function takes EDA report data and returns a matplotlib Figure.
Figures are self-contained and ready for embedding in HTML reports.

Convention: 10-Code_design §3.1 — single-responsibility per function.
Convention: 13-Data_ML §6.2 — stateless, no side effects.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for server environments

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Style defaults ───────────────────────────────────────────
PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B3", "#937860", "#DA8BC3", "#8C8C8C",
    "#CCB974", "#64B5CD",
]
FIG_DPI = 100
TITLE_SIZE = 13
LABEL_SIZE = 10


def _fig_to_base64(fig: plt.Figure) -> str:
    """Convert a matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def render_all_charts(report: Any) -> dict[str, str]:
    """Render all charts from an EdaReport, returning base64 PNGs.

    Args:
        report: EdaReport dataclass instance.

    Returns:
        Dict mapping chart_name → base64 PNG string.
    """
    charts: dict[str, str] = {}

    # Section A: Feature statistics
    if not report.descriptive_stats.empty:
        charts["distributions"] = _chart_distributions(report.descriptive_stats)

    if not report.missing_stats.empty:
        charts["missing_values"] = _chart_missing(report.missing_stats)

    if not report.outlier_stats.empty:
        charts["outlier_summary"] = _chart_outliers(report.outlier_stats)

    if not report.correlation_matrix.empty:
        charts["correlation_heatmap"] = _chart_correlation_heatmap(report.correlation_matrix)

    if not report.high_correlations.empty:
        charts["high_correlations"] = _chart_high_correlations(report.high_correlations)

    # Section B: Target analysis
    if report.class_distribution:
        charts["class_balance"] = _chart_class_balance(report.class_distribution)

    if report.point_biserial is not None and not report.point_biserial.empty:
        charts["point_biserial"] = _chart_point_biserial(report.point_biserial)

    if report.woe_iv is not None and not report.woe_iv.empty:
        charts["woe_iv"] = _chart_woe_iv(report.woe_iv)

    # Section C: Temporal analysis
    if report.monthly_drift is not None and not report.monthly_drift.empty:
        charts["monthly_drift"] = _chart_monthly_drift(report.monthly_drift)

    if report.feature_trends is not None and not report.feature_trends.empty:
        charts["feature_trends"] = _chart_feature_trends(report.feature_trends)

    logger.info("Rendered %d charts", len(charts))
    return charts


# ── Individual chart functions ──────────────────────────────


def _chart_distributions(stats: pd.DataFrame) -> str:
    """Bar chart of mean ± std for top features by magnitude."""
    top = stats.nlargest(15, "mean").copy()

    fig, ax = plt.subplots(figsize=(10, 6))
    y_pos = range(len(top))
    ax.barh(y_pos, top["mean"], xerr=top.get("std", 0), color=PALETTE[0], alpha=0.85, edgecolor="white")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(top.index, fontsize=LABEL_SIZE)
    ax.set_xlabel("Mean Value", fontsize=LABEL_SIZE)
    ax.set_title("Feature Distributions (Top 15 by Mean)", fontsize=TITLE_SIZE, fontweight="bold")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _chart_missing(missing: pd.DataFrame) -> str:
    """Horizontal bar chart of missing percentages."""
    has_missing = missing[missing["missing_pct"] > 0].sort_values("missing_pct", ascending=True)
    if has_missing.empty:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "No Missing Values Detected", ha="center", va="center",
                fontsize=14, color="#55A868", transform=ax.transAxes)
        ax.set_axis_off()
        fig.tight_layout()
        return _fig_to_base64(fig)

    top = has_missing.tail(20)  # Show top 20 with most missing
    fig, ax = plt.subplots(figsize=(10, max(4, len(top) * 0.35)))
    colors = [PALETTE[3] if v > 0.1 else PALETTE[0] for v in top["missing_pct"]]
    ax.barh(range(len(top)), top["missing_pct"] * 100, color=colors, alpha=0.85, edgecolor="white")
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(top.index, fontsize=LABEL_SIZE)
    ax.set_xlabel("Missing %", fontsize=LABEL_SIZE)
    ax.set_title("Missing Values (Features with Missing Data)", fontsize=TITLE_SIZE, fontweight="bold")
    ax.axvline(x=10, color=PALETTE[3], linestyle="--", alpha=0.5, label="10% threshold")
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _chart_outliers(outliers: pd.DataFrame) -> str:
    """Bar chart of outlier percentages by feature."""
    col = "iqr_outlier_pct" if "iqr_outlier_pct" in outliers.columns else outliers.columns[0]
    has_outliers = outliers[outliers[col] > 0].sort_values(col, ascending=True)
    if has_outliers.empty:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "No Significant Outliers Detected", ha="center", va="center",
                fontsize=14, color="#55A868", transform=ax.transAxes)
        ax.set_axis_off()
        fig.tight_layout()
        return _fig_to_base64(fig)

    top = has_outliers.tail(20)
    fig, ax = plt.subplots(figsize=(10, max(4, len(top) * 0.35)))
    colors = [PALETTE[3] if v > 0.05 else PALETTE[1] for v in top[col]]
    ax.barh(range(len(top)), top[col] * 100, color=colors, alpha=0.85, edgecolor="white")
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(top.index, fontsize=LABEL_SIZE)
    ax.set_xlabel("Outlier %", fontsize=LABEL_SIZE)
    ax.set_title("Outlier Analysis (IQR Method)", fontsize=TITLE_SIZE, fontweight="bold")
    ax.axvline(x=5, color=PALETTE[3], linestyle="--", alpha=0.5, label="5% threshold")
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _chart_correlation_heatmap(corr: pd.DataFrame) -> str:
    """Heatmap of correlation matrix."""
    n = min(len(corr), 25)  # Cap at 25 features for readability
    subset = corr.iloc[:n, :n]

    fig, ax = plt.subplots(figsize=(max(8, n * 0.5), max(6, n * 0.4)))
    im = ax.imshow(subset.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(subset.columns)))
    ax.set_yticks(range(len(subset.index)))
    ax.set_xticklabels(subset.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(subset.index, fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Correlation")
    ax.set_title("Feature Correlation Matrix", fontsize=TITLE_SIZE, fontweight="bold")
    fig.tight_layout()
    return _fig_to_base64(fig)


def _chart_high_correlations(high_corr: pd.DataFrame) -> str:
    """Bar chart of highly correlated feature pairs."""
    top = high_corr.head(20).copy()
    if "feature_1" in top.columns and "feature_2" in top.columns:
        labels = [f"{r['feature_1']} — {r['feature_2']}" for _, r in top.iterrows()]
    else:
        labels = [str(i) for i in range(len(top))]

    corr_col = "correlation" if "correlation" in top.columns else top.columns[-1]
    values = top[corr_col].values

    fig, ax = plt.subplots(figsize=(10, max(4, len(top) * 0.35)))
    colors = [PALETTE[3] if abs(v) > 0.9 else PALETTE[1] for v in values]
    ax.barh(range(len(labels)), np.abs(values), color=colors, alpha=0.85, edgecolor="white")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("|Correlation|", fontsize=LABEL_SIZE)
    ax.set_title("Highly Correlated Feature Pairs", fontsize=TITLE_SIZE, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _chart_class_balance(dist: dict) -> str:
    """Pie + bar chart for class distribution."""
    churn_rate = dist.get("churn_rate", 0)
    counts = dist.get("counts", {})

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Pie chart
    labels = ["Active", "Churned"]
    sizes = [1 - churn_rate, churn_rate]
    colors_pie = [PALETTE[2], PALETTE[3]]
    axes[0].pie(sizes, labels=labels, colors=colors_pie, autopct="%1.1f%%",
                startangle=90, textprops={"fontsize": 12})
    axes[0].set_title("Class Distribution", fontsize=TITLE_SIZE, fontweight="bold")

    # Bar chart with counts
    if counts:
        classes = list(counts.keys())
        vals = list(counts.values())
    else:
        classes = ["0 (Active)", "1 (Churned)"]
        total = dist.get("total", 1000)
        vals = [int(total * (1 - churn_rate)), int(total * churn_rate)]

    bar_colors = [PALETTE[2], PALETTE[3]][:len(classes)]
    axes[1].bar(classes, vals, color=bar_colors, alpha=0.85, edgecolor="white")
    axes[1].set_ylabel("Count", fontsize=LABEL_SIZE)
    axes[1].set_title("Class Counts", fontsize=TITLE_SIZE, fontweight="bold")
    for i, v in enumerate(vals):
        axes[1].text(i, v + max(vals) * 0.01, f"{v:,}", ha="center", fontsize=11)
    axes[1].grid(axis="y", alpha=0.3)

    fig.tight_layout()
    return _fig_to_base64(fig)


def _chart_point_biserial(pb: pd.DataFrame) -> str:
    """Sorted bar chart of point-biserial correlation with target."""
    col = "correlation" if "correlation" in pb.columns else pb.columns[0]
    sorted_pb = pb.sort_values(col, ascending=True).tail(20)

    fig, ax = plt.subplots(figsize=(10, max(4, len(sorted_pb) * 0.35)))
    colors = [PALETTE[3] if v > 0 else PALETTE[0] for v in sorted_pb[col]]
    ax.barh(range(len(sorted_pb)), sorted_pb[col], color=colors, alpha=0.85, edgecolor="white")
    ax.set_yticks(range(len(sorted_pb)))
    ax.set_yticklabels(sorted_pb.index, fontsize=LABEL_SIZE)
    ax.set_xlabel("Point-Biserial Correlation", fontsize=LABEL_SIZE)
    ax.set_title("Feature-Target Correlation (Top 20)", fontsize=TITLE_SIZE, fontweight="bold")
    ax.axvline(x=0, color="black", linewidth=0.5)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _chart_woe_iv(woe: pd.DataFrame) -> str:
    """IV importance bar chart sorted by Information Value."""
    iv_col = "iv" if "iv" in woe.columns else "IV"
    if iv_col not in woe.columns:
        iv_col = woe.columns[0]

    sorted_woe = woe.sort_values(iv_col, ascending=True).tail(20)

    fig, ax = plt.subplots(figsize=(10, max(4, len(sorted_woe) * 0.35)))

    def _iv_color(v: float) -> str:
        if v >= 0.3:
            return PALETTE[3]  # Strong
        if v >= 0.1:
            return PALETTE[1]  # Medium
        return PALETTE[0]  # Weak

    colors = [_iv_color(v) for v in sorted_woe[iv_col]]
    ax.barh(range(len(sorted_woe)), sorted_woe[iv_col], color=colors, alpha=0.85, edgecolor="white")
    ax.set_yticks(range(len(sorted_woe)))
    ax.set_yticklabels(sorted_woe.index, fontsize=LABEL_SIZE)
    ax.set_xlabel("Information Value (IV)", fontsize=LABEL_SIZE)
    ax.set_title("Feature Predictive Power (WoE/IV)", fontsize=TITLE_SIZE, fontweight="bold")
    # Thresholds
    ax.axvline(x=0.1, color=PALETTE[1], linestyle="--", alpha=0.5, label="Medium (0.1)")
    ax.axvline(x=0.3, color=PALETTE[3], linestyle="--", alpha=0.5, label="Strong (0.3)")
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _chart_monthly_drift(drift: pd.DataFrame) -> str:
    """PSI trend lines per feature over months."""
    psi_col = "psi" if "psi" in drift.columns else drift.columns[-1]
    month_col = "month" if "month" in drift.columns else drift.columns[0]
    feat_col = "feature" if "feature" in drift.columns else drift.columns[1]

    features = drift[feat_col].unique()[:8]  # Top 8 features

    fig, ax = plt.subplots(figsize=(12, 6))
    for i, feat in enumerate(features):
        feat_data = drift[drift[feat_col] == feat].sort_values(month_col)
        ax.plot(feat_data[month_col].astype(str), feat_data[psi_col],
                marker="o", label=feat, color=PALETTE[i % len(PALETTE)], linewidth=2)

    ax.axhline(y=0.1, color=PALETTE[3], linestyle="--", alpha=0.6, label="Alert threshold (0.1)")
    ax.set_xlabel("Month", fontsize=LABEL_SIZE)
    ax.set_ylabel("PSI", fontsize=LABEL_SIZE)
    ax.set_title("Monthly Feature Drift (PSI)", fontsize=TITLE_SIZE, fontweight="bold")
    ax.legend(fontsize=8, loc="upper left", ncol=2)
    ax.grid(alpha=0.3)
    plt.xticks(rotation=45)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _chart_feature_trends(trends: pd.DataFrame) -> str:
    """Bar chart of feature trend slopes."""
    slope_col = "slope" if "slope" in trends.columns else trends.columns[0]
    sorted_t = trends.sort_values(slope_col, key=abs, ascending=True).tail(15)

    fig, ax = plt.subplots(figsize=(10, max(4, len(sorted_t) * 0.35)))
    colors = [PALETTE[3] if v < 0 else PALETTE[2] for v in sorted_t[slope_col]]
    ax.barh(range(len(sorted_t)), sorted_t[slope_col], color=colors, alpha=0.85, edgecolor="white")
    ax.set_yticks(range(len(sorted_t)))
    ax.set_yticklabels(sorted_t.index, fontsize=LABEL_SIZE)
    ax.set_xlabel("Trend Slope", fontsize=LABEL_SIZE)
    ax.set_title("Feature Trends (Top 15 by |Slope|)", fontsize=TITLE_SIZE, fontweight="bold")
    ax.axvline(x=0, color="black", linewidth=0.5)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return _fig_to_base64(fig)
