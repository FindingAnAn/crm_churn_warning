"""EDA — Exploratory Data Analysis module for churn prediction.

Provides feature-level statistics, target analysis, temporal drift
detection, and baseline management.  Persist results to PostgreSQL
for historical tracking.

Public API
----------
- ``run_eda``            — one-call orchestrator
- ``EdaConfig``          — configuration dataclass
- ``EdaReport``          — result container
- ``ensure_eda_schema``  — DDL helper

Convention: 05-Module §3.1 — expose only the public surface.
"""

from data.eda.config import EdaConfig
from data.eda.report.builder import EdaReport
from data.eda.run_eda import run_eda

__all__ = ["EdaConfig", "EdaReport", "run_eda"]
