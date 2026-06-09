"""Typed application settings and configuration.

This module provides centralized, type-safe configuration management.
All runtime configuration is loaded through get_settings(), following
the conventions in docs/conventions/02-Config_conventions.md.

Example:
    >>> from src.settings import get_settings
    >>> config = get_settings()
    >>> print(config.db.sqlalchemy_url())
    >>> print(config.to_safe_dict())  # For logging

Subsystems:
    - Database: PostgreSQL connection (PostgresConfig)
    - File System: Ingestion paths (FSConfig)
    - Models: Training and serving artifacts (ModelPathsConfig)
    - Logging: Log level, format, output (LoggingConfig)
"""

from settings.application import AppSettings, get_settings
from settings.database import PostgresConfig
from settings.logging import LogFormat, LogLevel, LoggingConfig
from settings.paths import FSConfig, ModelPathsConfig, ensure_directories

__all__ = [
    # Main entry point
    "get_settings",
    # Root config
    "AppSettings",
    # Subsystem configs
    "PostgresConfig",
    "FSConfig",
    "ModelPathsConfig",
    "LoggingConfig",
    # Logging enums
    "LogLevel",
    "LogFormat",
    # Bootstrap helper
    "ensure_directories",
]

