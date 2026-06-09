"""Logging helpers for the engineering feature package."""

from __future__ import annotations

from core.logging import configure_logging
from core.logging import get_logger as _get_logger
from features.engineering.paths import get_engineering_logs_dir

LOG_DIR = get_engineering_logs_dir()


def setup_logging():
    """Configure logging once for the feature generation pipeline."""
    configure_logging(logs_dir=LOG_DIR, app_name="feature_pipeline")
    return _get_logger("feature_pipeline")


def get_logger(name: str):
    """Get a namespaced logger instance for this package."""
    return _get_logger(f"feature_pipeline.{name}")
