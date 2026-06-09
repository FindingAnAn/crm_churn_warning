"""Root application settings — composes all subsystem configs.

This module provides the centralized entry point for all configuration.
All subsystem configs are loaded and validated through get_settings().
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from settings.database import PostgresConfig
from settings.logging import LoggingConfig
from settings.paths import FSConfig, ModelPathsConfig


def get_settings(
    env_file: str | Path | None = None,
    *,
    skip_fs: bool = False,
    skip_logging: bool = False,
) -> AppSettings:
    """Load and validate all settings from environment.

    This is the centralized entry point for configuration. All runtime config
    must be loaded through this function, not scattered throughout the codebase.

    Args:
        env_file: Path to .env file. None = auto-detect in current directory.
        skip_fs: If True, skip FSConfig (useful for modeling-only tasks).
        skip_logging: If True, skip LoggingConfig (for testing or specific use cases).

    Returns:
        Validated AppSettings instance with all subsystem configs.

    Raises:
        OSError: If required environment variables (DB credentials) are missing.
        ValueError: If any config field fails validation.
    """
    # Load .env (idempotent — won't override existing env vars)
    if env_file:
        load_dotenv(env_file, override=False)
    else:
        load_dotenv(override=False)

    # ── Database config (always required)
    db = PostgresConfig.from_env()
    db.validate()

    # ── File system config (optional, ingestion pipeline only)
    fs = None
    if not skip_fs:
        try:
            fs = FSConfig.from_env()
            fs.validate()
        except (OSError, ValueError):
            # FS config is optional — some pipelines (modeling, serving) don't need it
            fs = None

    # ── Model paths config (always recommended)
    model_paths = ModelPathsConfig.from_env()
    model_paths.validate()

    # ── Logging config (optional, can be skipped for testing)
    logging_cfg = None
    if not skip_logging:
        try:
            logging_cfg = LoggingConfig.from_env()
            logging_cfg.validate()
        except (OSError, ValueError):
            # Logging config is optional — applications may configure logging separately
            logging_cfg = None

    return AppSettings(
        db=db,
        fs=fs,
        model_paths=model_paths,
        logging=logging_cfg,
    )


class AppSettings:
    """Root configuration container.

    Composes all subsystem configs and provides unified access.

    Attributes:
        db: PostgreSQL connection config (required).
        fs: File system paths config (optional, ingestion-only).
        model_paths: Model training and serving paths (required).
        logging: Logging and observability config (optional).
    """

    def __init__(
        self,
        db: PostgresConfig,
        model_paths: ModelPathsConfig,
        fs: FSConfig | None = None,
        logging: LoggingConfig | None = None,
    ) -> None:
        self.db = db
        self.fs = fs
        self.model_paths = model_paths
        self.logging = logging

    def to_safe_dict(self) -> dict:
        """Return all config as a safe-for-logging dict.

        Secrets are masked. Suitable for logging and debugging output.
        """
        result = {
            "db": self.db.to_safe_dict(),
            "model_paths": self.model_paths.to_safe_dict(),
        }
        if self.fs:
            result["fs"] = self.fs.to_safe_dict()
        if self.logging:
            result["logging"] = self.logging.to_safe_dict()
        return result

    def __repr__(self) -> str:
        """Safe representation for logging."""
        return (
            f"AppSettings("
            f"db={self.db}, "
            f"fs={self.fs}, "
            f"model_paths={self.model_paths}, "
            f"logging={self.logging})"
        )
