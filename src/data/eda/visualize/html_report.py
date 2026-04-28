"""Assemble EDA charts into a self-contained HTML report.

The report uses inline CSS and base64-encoded chart images,
so it can be opened in any browser without external dependencies.

Convention: 10-Code_design §3.1 — single responsibility.
Convention: 13-Data_ML §9.1 — idempotent output.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def build_html_report(
    charts: dict[str, str],
    metadata: dict,
    output_path: Path,
) -> Path:
    """Build a self-contained HTML report from chart images.

    Args:
        charts: Dict mapping chart_name → base64 PNG string.
        metadata: EDA run metadata (n_rows, n_features, config, etc.).
        output_path: Path to write the HTML file.

    Returns:
        Path to the generated HTML file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sections = _build_sections(charts, metadata)
    html = _render_html(sections, metadata)

    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML report saved to %s (%d KB)", output_path, len(html) // 1024)
    return output_path


# ── Section mapping ──────────────────────────────────────────
_SECTION_CONFIG = [
    {
        "key": "overview",
        "title": "📊 Data Overview",
        "charts": [],
        "type": "metadata",
    },
    {
        "key": "missing",
        "title": "🔍 Missing Values",
        "charts": ["missing_values"],
        "description": "Features with missing values and their percentages.",
    },
    {
        "key": "distributions",
        "title": "📈 Feature Distributions",
        "charts": ["distributions"],
        "description": "Distribution of feature values (top 15 by mean).",
    },
    {
        "key": "outliers",
        "title": "⚡ Outlier Analysis",
        "charts": ["outlier_summary"],
        "description": "Features with outliers detected using IQR method.",
    },
    {
        "key": "correlations",
        "title": "🔗 Correlations",
        "charts": ["correlation_heatmap", "high_correlations"],
        "description": "Feature correlation matrix and highly correlated pairs.",
    },
    {
        "key": "target",
        "title": "🎯 Target Analysis",
        "charts": ["class_balance", "point_biserial", "woe_iv"],
        "description": "Class distribution, feature-target correlation, and predictive power.",
    },
    {
        "key": "temporal",
        "title": "📅 Temporal Analysis",
        "charts": ["monthly_drift", "feature_trends"],
        "description": "Feature drift over time and trend analysis.",
    },
]


def _build_sections(charts: dict[str, str], metadata: dict) -> list[dict]:
    """Build section data from available charts."""
    sections = []

    for cfg in _SECTION_CONFIG:
        if cfg.get("type") == "metadata":
            sections.append({
                "title": cfg["title"],
                "content": _render_overview_html(metadata),
            })
            continue

        available = [c for c in cfg["charts"] if c in charts]
        if not available:
            continue

        img_html = "\n".join(
            f'<img src="data:image/png;base64,{charts[c]}" alt="{c}" class="chart-img">'
            for c in available
        )

        sections.append({
            "title": cfg["title"],
            "description": cfg.get("description", ""),
            "content": img_html,
        })

    return sections


def _render_overview_html(metadata: dict) -> str:
    """Render the data overview section as an HTML table."""
    rows = [
        ("Total Rows", f"{metadata.get('n_rows', 'N/A'):,}" if isinstance(metadata.get('n_rows'), int) else metadata.get('n_rows', 'N/A')),
        ("Total Features", metadata.get("n_features", "N/A")),
        ("Has Target", "Yes" if metadata.get("has_target") else "No"),
        ("Has Temporal", "Yes" if metadata.get("has_temporal") else "No"),
        ("Generated At", metadata.get("timestamp", datetime.now(tz=timezone.utc).isoformat())),
    ]

    table_rows = "\n".join(
        f"<tr><td class='meta-key'>{k}</td><td class='meta-val'>{v}</td></tr>"
        for k, v in rows
    )

    return f"""
    <table class="overview-table">
        <tbody>{table_rows}</tbody>
    </table>
    """


def _render_html(sections: list[dict], metadata: dict) -> str:
    """Render the complete HTML report."""
    timestamp = metadata.get("timestamp", datetime.now(tz=timezone.utc).isoformat())

    sections_html = "\n".join(
        f"""
        <section class="report-section">
            <h2>{s['title']}</h2>
            {f"<p class='section-desc'>{s.get('description', '')}</p>" if s.get('description') else ""}
            <div class="chart-container">
                {s['content']}
            </div>
        </section>
        """
        for s in sections
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Churn EDA Report — {timestamp[:10]}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --border: #334155;
            --text: #e2e8f0;
            --text-muted: #94a3b8;
            --accent: #60a5fa;
            --accent2: #818cf8;
            --success: #34d399;
            --danger: #f87171;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}
        header {{
            text-align: center;
            padding: 3rem 0 2rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 2rem;
        }}
        header h1 {{
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}
        header p {{
            color: var(--text-muted);
            font-size: 0.95rem;
        }}
        .report-section {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem 2rem;
            margin-bottom: 1.5rem;
        }}
        .report-section h2 {{
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
            color: var(--accent);
        }}
        .section-desc {{
            color: var(--text-muted);
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }}
        .chart-container {{
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            align-items: center;
        }}
        .chart-img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        .overview-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .overview-table tr {{
            border-bottom: 1px solid var(--border);
        }}
        .overview-table td {{
            padding: 0.75rem 1rem;
        }}
        .meta-key {{
            color: var(--text-muted);
            font-weight: 500;
            width: 40%;
        }}
        .meta-val {{
            color: var(--text);
            font-weight: 600;
        }}
        footer {{
            text-align: center;
            padding: 2rem 0;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Churn Prediction — EDA Report</h1>
            <p>Generated: {timestamp} | Features: {metadata.get('n_features', 'N/A')} | Rows: {metadata.get('n_rows', 'N/A'):,}</p>
        </header>

        {sections_html}

        <footer>
            <p>Churn Prediction EDA Pipeline — Auto-generated report</p>
        </footer>
    </div>
</body>
</html>"""
