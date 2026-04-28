"""Month-over-month feature drift using PSI and KS.

Reuses statistical primitives from the monitoring layer:
``monitoring.model_quality.monitoring.psi``.

Convention: 10-Code_design §2.1 — one coherent responsibility.
"""

from __future__ import annotations

import logging

import pandas as pd

from monitoring.model_quality.monitoring.psi import (
    counts_on_profile,
    discrete_ks_from_counts,
    make_numeric_profile,
    psi_from_counts,
)

logger = logging.getLogger(__name__)


def _severity(psi: float) -> str:
    """Classify PSI into severity levels."""
    if psi > 0.2:
        return "ALERT"
    if psi > 0.1:
        return "WARN"
    return "OK"


def compute_monthly_drift(
    dfs_by_month: dict[int, pd.DataFrame],
    feature_cols: list[str],
    n_bins: int = 10,
) -> pd.DataFrame:
    """Compare feature distributions across monthly snapshots.

    The earliest month in *dfs_by_month* is used as the reference
    profile.  Each subsequent month is compared against it.

    Parameters
    ----------
    dfs_by_month : dict[int, pd.DataFrame]
        Mapping ``YYMM`` -> DataFrame for each month.
    feature_cols : list[str]
        Features to analyse.
    n_bins : int
        Bins for distribution profiling.

    Returns
    -------
    pd.DataFrame
        Columns: ``reference_month, comparison_month, feature_name,
        psi, ks_stat, severity``.
        Empty DataFrame when fewer than 2 months are provided.
    """
    sorted_months = sorted(dfs_by_month.keys())
    if len(sorted_months) < 2:
        logger.warning(
            "Temporal drift requires >= 2 months; got %d", len(sorted_months),
        )
        return pd.DataFrame(
            columns=[
                "reference_month", "comparison_month",
                "feature_name", "psi", "ks_stat", "severity",
            ],
        )

    ref_month = sorted_months[0]
    ref_df = dfs_by_month[ref_month]
    rows: list[dict] = []

    # Build profiles from reference month
    profiles: dict[str, dict] = {}
    for col in feature_cols:
        if col not in ref_df.columns:
            continue
        prof = make_numeric_profile(ref_df[col], n_bins=n_bins)
        if prof is not None:
            profiles[col] = prof

    # Compare each subsequent month
    for cmp_month in sorted_months[1:]:
        cmp_df = dfs_by_month[cmp_month]
        for col, prof in profiles.items():
            if col not in cmp_df.columns:
                rows.append({
                    "reference_month": ref_month,
                    "comparison_month": cmp_month,
                    "feature_name": col,
                    "psi": None,
                    "ks_stat": None,
                    "severity": "ALERT",
                })
                continue

            import numpy as np

            train_counts = np.array(prof["train_counts"], dtype=float)
            cur_counts = counts_on_profile(cmp_df[col], prof)
            psi = psi_from_counts(train_counts, cur_counts)
            ks = discrete_ks_from_counts(train_counts, cur_counts)
            rows.append({
                "reference_month": ref_month,
                "comparison_month": cmp_month,
                "feature_name": col,
                "psi": round(float(psi), 6),
                "ks_stat": round(float(ks), 6),
                "severity": _severity(psi),
            })

    return pd.DataFrame(rows)
