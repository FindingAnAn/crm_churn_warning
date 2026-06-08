"""Tests for leakage-safe lifetime-as-of feature SQL."""

from __future__ import annotations

from src.features.engineering.aggregation.window_features.lifetime_asof import render_lifetime_asof_sql


def test_lifetime_asof_sql_uses_upper_time_bound():
    """Lifetime-as-of must stop at the feature window end."""
    _, insert_sql = render_lifetime_asof_sql(
        "data_window.cus_lifetime_3m_2501_2503",
        "2025-01-01",
        "2025-03-31",
    )

    assert "report_month <= DATE '2025-03-31'" in insert_sql
    assert "report_month >= DATE '2025-01-01'" in insert_sql
    assert "data_static.cus_lifetime" not in insert_sql
