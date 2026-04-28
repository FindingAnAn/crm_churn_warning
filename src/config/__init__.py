# config/ — Centralized configuration module.
# Conventions: 02-Config §3.3 — all config code in dedicated module.

from config.settings import get_settings

__all__ = ["get_settings"]
