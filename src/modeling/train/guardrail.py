"""Post-training guardrail checks.

Convention: 13-Data_ML §8.2 — minimum quality gates before deployment.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def check_guardrail(
    metrics: dict,
    *,
    min_f05: float = 0.10,
    min_pr_auc: float = 0.05,
) -> tuple[bool, str]:
    """Check if model metrics meet minimum quality thresholds.

    Args:
        metrics: Dict from evaluate_model (must contain 'f05', 'pr_auc').
        min_f05: Minimum acceptable F0.5 score.
        min_pr_auc: Minimum acceptable PR-AUC.

    Returns:
        Tuple of (passed: bool, reason: str).
    """
    f05 = metrics.get("f05", 0.0)
    pr_auc = metrics.get("pr_auc", 0.0)

    reasons = []
    if f05 < min_f05:
        reasons.append(f"F0.5={f05:.4f} < min_f05={min_f05}")
    if pr_auc < min_pr_auc:
        reasons.append(f"PR-AUC={pr_auc:.4f} < min_pr_auc={min_pr_auc}")

    if reasons:
        msg = "GUARDRAIL FAILED: " + "; ".join(reasons)
        logger.warning(msg)
        return False, msg

    msg = f"Guardrail passed: F0.5={f05:.4f} >= {min_f05}, PR-AUC={pr_auc:.4f} >= {min_pr_auc}"
    logger.info(msg)
    return True, msg


def check_accept_reject(
    new_f05: float,
    prev_f05: float | None,
    *,
    eps: float = 1e-6,
) -> tuple[bool, str]:
    """Decide whether to accept the new model over the previous.

    Args:
        new_f05: F0.5 score of the new candidate model.
        prev_f05: F0.5 score of the previously accepted model (None = first run).
        eps: Minimum improvement required.

    Returns:
        Tuple of (accepted: bool, rule: str).
    """
    if prev_f05 is None:
        rule = "accepted_no_previous"
        logger.info("Accept decision: %s (first model)", rule)
        return True, rule

    improved = new_f05 > (prev_f05 + eps)
    if improved:
        rule = f"accepted_f05_improved ({prev_f05:.4f} → {new_f05:.4f})"
    else:
        rule = f"rejected_f05_not_improved ({prev_f05:.4f} → {new_f05:.4f}, eps={eps})"

    logger.info("Accept decision: %s", rule)
    return improved, rule
