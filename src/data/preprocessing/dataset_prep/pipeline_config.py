"""Pipeline configuration for the dataset preparation steps.

All hyperparameters and thresholds from the notebook CONFIG BLOCK
are centralized here as a typed, validated Pydantic model.

Conventions applied:
  - 02-Config §3.1: One config per subsystem.
  - 02-Config §5.1: Strong typing.
  - 02-Config §6.1: Self-validating.
  - 13-Data_ML §7.2: Hyperparameters through config, not hardcoded.
  - 13-Data_ML §9.4: Pipeline config externalized.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class DatasetPipelineConfig:
    """Configuration for the 7-step dataset preparation pipeline.

    Attributes:
        horizon_months: H — prediction horizon in months.
        step_months: Sliding window step size.
        gap_days: Gap between feature window end and label start.
        w_min: Minimum window size to search.
        min_train_windows: Minimum folds for walk-forward validation.
        data_start: Earliest date to consider for feature computation.
        t_obs_override: Override observation date (None = auto-detect).

        min_lifetime_orders: Scope filter — minimum lifetime order count.
        min_account_age_days: Scope filter — minimum account age.
        max_inactive_days: Scope filter — max days since last order.

        recency_active: Tier boundary for 'active' (days).
        recency_at_risk: Tier boundary for 'at_risk' (days).
        recency_reliable_neg: Recency threshold for reliable negative.

        alpha_ewma: EWMA smoothing parameter.
        sim_threshold: Similarity threshold for pseudo-labeling.
        sigma_reg: Regularization for covariance matrix inversion.

        label_smooth_eps_confirmed: Label smoothing for confirmed.
        label_smooth_eps_tier: Label smoothing for tier-based.
        label_smooth_eps_pseudo: Label smoothing for pseudo-labeled.

        cskh_file_path: Path to CSKH confirmed churn file (optional).
    """

    # ── Window & horizon ──────────────────────────────────
    horizon_months: int = 2
    step_months: int = 1
    gap_days: int = 0
    w_min: int = 3
    min_train_windows: int = 5
    data_start: date = field(default_factory=lambda: date(2025, 1, 1))
    t_obs_override: date | None = None

    # ── Scope filter ──────────────────────────────────────
    min_lifetime_orders: int = 3
    min_lifetime_gmv: float = 0.0
    min_account_age_days: int = 30
    max_inactive_days: int = 365

    # ── Tiering ───────────────────────────────────────────
    recency_active: int = 90
    recency_at_risk: int = 180
    recency_reliable_neg: int = 30

    # ── EWMA & similarity ─────────────────────────────────
    alpha_ewma: float = 0.3
    sim_threshold: float = 0.80
    sigma_reg: float = 0.01

    # ── Label smoothing ───────────────────────────────────
    label_smooth_eps_confirmed: float = 0.00
    label_smooth_eps_tier: float = 0.05
    label_smooth_eps_pseudo: float = 0.10

    # ── Pseudo-labeling ───────────────────────────────────
    trend_down_ratio: float = 0.85

    # ── PU learning ───────────────────────────────────────
    pu_weight_min: float = 0.01

    # ── Prototype ─────────────────────────────────────────
    min_prototype_samples: int = 10

    # ── CSKH file ─────────────────────────────────────────
    cskh_file_path: Path | None = None
    cskh_dir: Path | None = None

    # ── Fallback behavior (khi không có file CSKH) ────────
    allow_prototype_fallback: bool = True
    max_prototype_age_months: int = 3
    fallback_pu_weight: float = 0.05

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If any parameter is invalid.
        """
        if self.horizon_months < 1:
            raise ValueError(f"horizon_months must be >= 1, got {self.horizon_months}")
        if self.w_min < 2:
            raise ValueError(f"w_min must be >= 2, got {self.w_min}")
        if self.min_train_windows < 2:
            raise ValueError(f"min_train_windows must be >= 2, got {self.min_train_windows}")
        if not (0 < self.alpha_ewma < 1):
            raise ValueError(f"alpha_ewma must be in (0, 1), got {self.alpha_ewma}")
        if not (0 <= self.sim_threshold <= 1):
            raise ValueError(f"sim_threshold must be in [0, 1], got {self.sim_threshold}")
        if self.recency_active >= self.recency_at_risk:
            raise ValueError(
                f"recency_active ({self.recency_active}) must be < recency_at_risk ({self.recency_at_risk})"
            )

    def to_safe_dict(self) -> dict:
        """Return config as a logging-safe dictionary."""
        return {
            "horizon_months": self.horizon_months,
            "w_min": self.w_min,
            "data_start": str(self.data_start),
            "t_obs_override": str(self.t_obs_override) if self.t_obs_override else None,
            "min_lifetime_orders": self.min_lifetime_orders,
            "recency_active": self.recency_active,
            "recency_at_risk": self.recency_at_risk,
            "alpha_ewma": self.alpha_ewma,
            "sim_threshold": self.sim_threshold,
        }


# ── Numeric features list (from notebook) ─────────────────
# Convention: 13-Data_ML §6.1 — snake_case, prefixed by domain.
NUMERIC_FEATURES: list[str] = [
    "item_sum",
    "item_avg",
    "item_std",
    "item_median",
    "revenue_sum",
    "revenue_avg",
    "revenue_std",
    "complaint_sum",
    "complaint_avg",
    "weight_sum",
    "weight_avg",
    "avg_revenue_per_item",
    "pct_delay",
    "pct_refund",
    "pct_noaccepted",
    "pct_lost_order",
    "pct_complaint",
    "pct_successful_item",
    "pct_intra_province",
    "pct_international",
    "avg_delayday",
    "order_score_avg",
    "satisfaction_avg",
    "active_months",
    "inactive_months",
    "active_days",
    "inactive_days",
    "avg_noservice_days",
    "avg_lastday",
    "item_slope",
    "revenue_slope",
    "satisfy_slope",
    "complaint_slope",
    "cv_item",
    "cv_revenue",
    "item_range",
    "revenue_range",
    "service_types_used",
    "dominant_service_ratio",
    "ser_c_sum",
    "ser_e_sum",
    "ser_m_sum",
    "ser_p_sum",
    "ser_r_sum",
    "ser_u_sum",
    "ser_l_sum",
    "ser_q_sum",
    "recency",
    "frequency",
    "monetary",
    # Multi-signal EWMA features
    "ewma_item",
    "delta_ewma_item",
    "ewma_revenue",
    "delta_ewma_revenue",
    "ewma_complaint",
    "delta_ewma_complaint",
    "ewma_delay",
    "delta_ewma_delay",
    "ewma_nodone",
    "delta_ewma_nodone",
    "ewma_order",
    "delta_ewma_order",
    "ewma_satisfaction",
    "delta_ewma_satisfaction",
    # Legacy aliases (backward compat)
    "ewma",
    "delta_ewma",
]
