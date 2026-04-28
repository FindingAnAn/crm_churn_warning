"""Root application settings — composes all subsystem configs.

Conventions applied:
  - 02-Config §3.2: One root config (AppSettings) composing subsystem configs.
  - 02-Config §4.1: Centralized loading via get_settings().
  - 02-Config §4.3: Only this module calls os.getenv / load_dotenv.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from config.db_config import PostgresConfig
from config.paths import FSConfig, ModelPathsConfig


def get_settings(
    env_file: str | Path | None = None,
    *,
    skip_fs: bool = False,
) -> AppSettings:
    """Load and validate all settings from environment.

    Args:
        env_file: Path to .env file. None = auto-detect.
        skip_fs: If True, skip FSConfig (useful for modeling-only tasks).

    Returns:
        Validated AppSettings instance.
    """
    # Load .env (idempotent — won't override existing env vars)
    if env_file:
        load_dotenv(env_file, override=False)
    else:
        load_dotenv(override=False)

    db = PostgresConfig.from_env()
    db.validate()

    fs = None
    if not skip_fs:
        try:
            fs = FSConfig.from_env()
            fs.validate()
        except OSError:
            fs = None  # FS not required for all pipelines

    model_paths = ModelPathsConfig.from_env()
    model_paths.validate()

    return AppSettings(db=db, fs=fs, model_paths=model_paths)


class AppSettings:
    """Root configuration container.

    Attributes:
        db: PostgreSQL connection config.
        fs: File system paths (optional, ingestion-only).
        model_paths: Model pipeline paths.
    """

    def __init__(
        self,
        db: PostgresConfig,
        fs: FSConfig | None,
        model_paths: ModelPathsConfig,
    ) -> None:
        self.db = db
        self.fs = fs
        self.model_paths = model_paths

    def to_safe_dict(self) -> dict:
        """Return all config as a safe-for-logging dict."""
        result = {"db": self.db.to_safe_dict()}
        if self.fs:
            result["fs"] = self.fs.to_safe_dict()
        result["model_paths"] = self.model_paths.to_safe_dict()
        return result
