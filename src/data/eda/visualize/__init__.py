"""EDA visualization package.

Convention: 01-Structure §7.3 — visualization under src/data/eda/.
"""

from data.eda.visualize.charts import render_all_charts
from data.eda.visualize.html_report import build_html_report

__all__ = ["render_all_charts", "build_html_report"]
