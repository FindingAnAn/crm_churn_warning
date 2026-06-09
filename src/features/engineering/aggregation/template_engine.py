"""Template loading and rendering engine for SQL assets."""

from __future__ import annotations

from typing import Any

from features.engineering.paths import get_engineering_sql_dir

SQL_DIR = get_engineering_sql_dir()

# Cache templates in memory for reuse
_TEMPLATE_CACHE: dict[str, str] = {}

TEMPLATE_PATHS = {
    'lifetime_aggregate': SQL_DIR / 'data_static' / 'lifetime_aggregate.sql',
    'lifetime_table': SQL_DIR / 'data_static' / 'lifetime_template.sql',
    'sliding_aggregate': SQL_DIR / 'data_window' / 'sliding_aggregate.sql',
    'sliding_table': SQL_DIR / 'data_window' / 'sliding_template.sql'
}


def get_template(name: str) -> str:
    """Get template from cache or load from disk once."""
    if name not in _TEMPLATE_CACHE:
        path = TEMPLATE_PATHS.get(name)
        if not path:
            raise ValueError(f"Unknown template: {name}")
        _TEMPLATE_CACHE[name] = path.read_text(encoding='utf-8')
    return _TEMPLATE_CACHE[name]


def render_template(name: str, **kwargs: Any) -> str:
    template = get_template(name)
    # Build replacement dict once to avoid redundant dictionary lookups
    replacements = {'{' + k + '}': str(v) for k, v in kwargs.items()}
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def clear_cache():
    global _TEMPLATE_CACHE
    _TEMPLATE_CACHE.clear()
