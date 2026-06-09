"""Model training configuration.

"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """XGBoost hyperparameters for churn prediction.

    Attributes:
        max_depth: Maximum tree depth.
        learning_rate: Boosting learning rate (eta).
        n_estimators: Maximum boosting rounds.
        subsample: Row sampling ratio per tree.
        colsample_bytree: Column sampling ratio per tree.
        min_child_weight: Minimum sum of instance weight in a child.
        gamma: Minimum loss reduction for further partition.
        reg_alpha: L1 regularization on weights.
        reg_lambda: L2 regularization on weights.
        early_stopping_rounds: Stop if eval metric doesn't improve.
        eval_metric: Metric(s) for evaluation during training.
        scale_pos_weight: Set to 1.0 — PU weights handled via sample_weight.
        random_state: Reproducibility seed.
    """

    # ── Tree structure ────────────────────────────────────
    max_depth: int = 6
    min_child_weight: int = 5
    gamma: float = 0.1

    # ── Boosting ──────────────────────────────────────────
    learning_rate: float = 0.05
    n_estimators: int = 500
    early_stopping_rounds: int = 30

    # ── Regularization ────────────────────────────────────
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0

    # ── Evaluation ────────────────────────────────────────
    eval_metric: list[str] = field(default_factory=lambda: ["logloss", "aucpr"])
    scale_pos_weight: float = 1.0

    # ── Guardrail thresholds ──────────────────────────────
    min_f2: float = 0.10
    min_roc_auc: float = 0.05
    f2_improve_eps: float = 1e-6

    # ── Scoring ───────────────────────────────────────────
    risk_threshold_pct: float = 90.0

    # ── Misc ──────────────────────────────────────────────
    random_state: int = 42

    def validate(self) -> None:
        """Validate configuration values.

        """
        if self.max_depth < 1:
            raise ValueError(f"max_depth must be >= 1, got {self.max_depth}")
        if not (0 < self.learning_rate <= 1):
            raise ValueError(f"learning_rate must be in (0, 1], got {self.learning_rate}")
        if self.n_estimators < 1:
            raise ValueError(f"n_estimators must be >= 1, got {self.n_estimators}")
        if not (0 < self.subsample <= 1):
            raise ValueError(f"subsample must be in (0, 1], got {self.subsample}")
        if not (0 < self.colsample_bytree <= 1):
            raise ValueError(f"colsample_bytree must be in (0, 1], got {self.colsample_bytree}")
        if not (0 <= self.risk_threshold_pct <= 100):
            raise ValueError(f"risk_threshold_pct must be in [0, 100], got {self.risk_threshold_pct}")

    @property
    def min_f1(self) -> float:
        """Backward-compatible alias for the current F0.5 guardrail."""
        return self.min_f2

    @property
    def min_pr_auc(self) -> float:
        """Backward-compatible alias for the current PR-AUC guardrail."""
        return self.min_roc_auc

    @property
    def f1_improve_eps(self) -> float:
        """Backward-compatible alias for the current F0.5 improvement epsilon."""
        return self.f2_improve_eps

    def to_xgb_params(self) -> dict:
        """Convert to XGBoost parameter dict."""
        return {
            "objective": "binary:logistic",
            "eval_metric": self.eval_metric,
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
            "subsample": self.subsample,
            "colsample_bytree": self.colsample_bytree,
            "min_child_weight": self.min_child_weight,
            "gamma": self.gamma,
            "reg_alpha": self.reg_alpha,
            "reg_lambda": self.reg_lambda,
            "scale_pos_weight": self.scale_pos_weight,
            "seed": self.random_state,
            "verbosity": 1,
        }

    def to_safe_dict(self) -> dict:
        """Return config as a logging-safe dictionary."""
        return {
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
            "n_estimators": self.n_estimators,
            "subsample": self.subsample,
            "colsample_bytree": self.colsample_bytree,
            "early_stopping_rounds": self.early_stopping_rounds,
            "min_f05": self.min_f1,
            "min_pr_auc": self.min_pr_auc,
            "f05_improve_eps": self.f1_improve_eps,
            "risk_threshold_pct": self.risk_threshold_pct,
        }
