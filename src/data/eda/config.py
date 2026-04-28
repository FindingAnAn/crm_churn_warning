"""EDA configuration — single config per subsystem.

Conventions applied:
  - 02-Config §3.1: One config per subsystem.
  - 02-Config §5.1: Strong typing via frozen dataclass.
  - 02-Config §6.1: Self-validating.
  - 13-Data_ML §9.4: Pipeline config externalized.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from data.preprocessing.dataset_prep.pipeline_config import NUMERIC_FEATURES


def _default_features() -> list[str]:
    return list(NUMERIC_FEATURES)


def _default_percentiles() -> list[float]:
    return [0.05, 0.25, 0.50, 0.75, 0.95]


@dataclass(frozen=True)
class EdaConfig:
    """Configuration for the EDA analysis pipeline.

    Attributes
    ----------
    feature_cols : list[str]
        Features to analyse.  Defaults to ``NUMERIC_FEATURES``.
    percentiles : list[float]
        Quantiles reported in descriptive stats.
    outlier_iqr_factor : float
        IQR multiplier for outlier fences (default 1.5).
    outlier_zscore_threshold : float
        Z-score threshold for outlier detection (default 3.0).
    correlation_method : str
        ``"pearson"`` or ``"spearman"``.
    correlation_threshold : float
        Minimum |r| to persist a correlation pair.
    n_bins : int
        Bin count for distribution profiling / WoE.
    woe_min_pct : float
        Minimum bin proportion for WoE (Laplace guard).
    temporal_window_months : int
        How many months back for temporal analysis.
    is_baseline_run : bool
        Whether to save current run as baseline snapshot.
    schema : str
        PostgreSQL schema for EDA tables.
    visualize : bool
        Whether to generate HTML report with charts.
    report_dir : Path
        Output directory for HTML reports.
    """

    feature_cols: list[str] = field(default_factory=_default_features)
    percentiles: list[float] = field(default_factory=_default_percentiles)

    # Outlier detection
    outlier_iqr_factor: float = 1.5
    outlier_zscore_threshold: float = 3.0

    # Correlation
    correlation_method: Literal["pearson", "spearman"] = "pearson"
    correlation_threshold: float = 0.80

    # Binning
    n_bins: int = 10
    woe_min_pct: float = 0.05

    # Temporal
    temporal_window_months: int = 6

    # Baseline
    is_baseline_run: bool = False

    # Schema
    schema: str = "eda_reports"

    # Visualization
    visualize: bool = False
    report_dir: Path = field(default_factory=lambda: Path("reports/eda"))

    # ── Validation ───────────────────────────────────────
    def validate(self) -> None:
        """Validate all config values.

        Raises
        ------
        ValueError
            If any parameter is out of range.
        """
        if not self.feature_cols:
            raise ValueError("feature_cols must not be empty")
        if self.outlier_iqr_factor <= 0:
            raise ValueError(
                f"outlier_iqr_factor must be > 0, got {self.outlier_iqr_factor}"
            )
        if self.outlier_zscore_threshold <= 0:
            raise ValueError(
                f"outlier_zscore_threshold must be > 0, "
                f"got {self.outlier_zscore_threshold}"
            )
        if self.correlation_method not in ("pearson", "spearman"):
            raise ValueError(
                f"correlation_method must be 'pearson' or 'spearman', "
                f"got '{self.correlation_method}'"
            )
        if not (0 < self.correlation_threshold <= 1):
            raise ValueError(
                f"correlation_threshold must be in (0, 1], "
                f"got {self.correlation_threshold}"
            )
        if self.n_bins < 2:
            raise ValueError(f"n_bins must be >= 2, got {self.n_bins}")
        if not (0 < self.woe_min_pct < 1):
            raise ValueError(
                f"woe_min_pct must be in (0, 1), got {self.woe_min_pct}"
            )
        if self.temporal_window_months < 1:
            raise ValueError(
                f"temporal_window_months must be >= 1, "
                f"got {self.temporal_window_months}"
            )

    # ── Logging-safe representation ──────────────────────
    def to_safe_dict(self) -> dict:
        """Return config as a logging-safe dictionary."""
        return {
            "n_features": len(self.feature_cols),
            "percentiles": self.percentiles,
            "outlier_iqr_factor": self.outlier_iqr_factor,
            "outlier_zscore_threshold": self.outlier_zscore_threshold,
            "correlation_method": self.correlation_method,
            "correlation_threshold": self.correlation_threshold,
            "n_bins": self.n_bins,
            "woe_min_pct": self.woe_min_pct,
            "temporal_window_months": self.temporal_window_months,
            "is_baseline_run": self.is_baseline_run,
            "schema": self.schema,
            "visualize": self.visualize,
            "report_dir": str(self.report_dir),
        }
