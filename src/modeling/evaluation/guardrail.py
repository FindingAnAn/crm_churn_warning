"""Post-training guardrail checks.

"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def check_guardrail(
    metrics: dict,
    *,
    min_f05: float = 0.10,
    min_pr_auc: float = 0.05,
    min_f2: float | None = None,
    min_roc_auc: float | None = None,
) -> tuple[bool, str]:
    """Check if model metrics meet minimum quality thresholds.

    Args:
        metrics: Dict from evaluate_model.
        min_f05: Minimum acceptable F0.5 score.
        min_pr_auc: Minimum acceptable PR-AUC.

    Returns:
        Tuple of (passed: bool, reason: str).
    """
    score_key = "f05" if "f05" in metrics else "f2"
    auc_key = "pr_auc" if "pr_auc" in metrics else "roc_auc"
    score_label = "F0.5" if score_key == "f05" else "F2"
    auc_label = "PR-AUC" if auc_key == "pr_auc" else "ROC-AUC"

    score_min = min_f05 if min_f2 is None else min_f2
    auc_min = min_pr_auc if min_roc_auc is None else min_roc_auc
    score = metrics.get(score_key, 0.0)
    auc = metrics.get(auc_key, 0.0)

    reasons = []
    if score < score_min:
        reasons.append(f"{score_label}={score:.4f} < min={score_min}")
    if auc < auc_min:
        reasons.append(f"{auc_label}={auc:.4f} < min={auc_min}")

    if reasons:
        msg = "GUARDRAIL FAILED: " + "; ".join(reasons)
        logger.warning(msg)
        return False, msg

    msg = f"Guardrail passed: {score_label}={score:.4f} >= {score_min}, {auc_label}={auc:.4f} >= {auc_min}"
    logger.info(msg)
    return True, msg


def check_accept_reject(
    new_f05: float,
    prev_f05: float | None = None,
    *,
    eps: float = 1e-6,
    prev_f2: float | None = None,
) -> tuple[bool, str]:
    """Decide whether to accept the new model over the previous.

    Args:
        new_f05: F0.5 score of the new candidate model.
        prev_f05: F0.5 score of the previously accepted model (None = first run).
        eps: Minimum improvement required.

    Returns:
        Tuple of (accepted: bool, rule: str).
    """
    if prev_f05 is None and prev_f2 is not None:
        prev_f05 = prev_f2

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
