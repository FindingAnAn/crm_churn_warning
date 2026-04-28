"""File system path configuration.

Conventions applied:
  - 02-Config §3.1: One config per subsystem (FSConfig).
  - 02-Config §5.2: Use Path for file paths.
  - 02-Config §6.2: Validation must not mutate system state.
  - 02-Config §9.2: Env vars uppercase with FS_ / MODEL_ prefix.
  - 02-Config §10.2: Bootstrap (mkdir) is separate from validation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FSConfig:
    """File system paths for the ingestion pipeline.

    Attributes:
        incoming_dir: Directory where incoming ZIP files are received.
        saved_dir: Directory for successfully processed data.
        fail_dir: Directory for data that failed processing.
    """

    incoming_dir: Path
    saved_dir: Path
    fail_dir: Path

    @classmethod
    def from_env(cls) -> FSConfig:
        """Load paths from environment variables.

        Required env vars:
            INCOMING_DIR, SAVED_DIR, FAIL_DIR
        """
        return cls(
            incoming_dir=_get_required_path("INCOMING_DIR"),
            saved_dir=_get_required_path("SAVED_DIR"),
            fail_dir=_get_required_path("FAIL_DIR"),
        )

    def validate(self) -> None:
        """Validate that path values are non-empty.

        NOTE: Does NOT check existence or create directories.
              That belongs in bootstrap code (02-Config §10.2).
        """
        for field_name in ("incoming_dir", "saved_dir", "fail_dir"):
            value = getattr(self, field_name)
            if not str(value).strip():
                raise ValueError(f"FSConfig.{field_name} must not be empty.")

    def to_safe_dict(self) -> dict[str, str]:
        """Return config as a dict safe for logging."""
        return {
            "incoming_dir": str(self.incoming_dir),
            "saved_dir": str(self.saved_dir),
            "fail_dir": str(self.fail_dir),
        }


@dataclass(frozen=True)
class ModelPathsConfig:
    """File system paths for the modeling pipeline.

    Attributes:
        model_dir: Root directory for model bundles and artifacts.
        logs_dir: Directory for pipeline logs.
    """

    model_dir: Path
    logs_dir: Path

    @classmethod
    def from_env(cls) -> ModelPathsConfig:
        """Load paths from environment variables."""
        return cls(
            model_dir=Path(os.getenv("CHURN_MODEL_DIR", "./model_bundles")),
            logs_dir=Path(os.getenv("LOGS_DIR", "./logs")),
        )

    def validate(self) -> None:
        """Validate path values are non-empty."""
        if not str(self.model_dir).strip():
            raise ValueError("ModelPathsConfig.model_dir must not be empty.")

    def to_safe_dict(self) -> dict[str, str]:
        """Return config as a dict safe for logging."""
        return {
            "model_dir": str(self.model_dir),
            "logs_dir": str(self.logs_dir),
        }


def ensure_directories(*paths: Path) -> None:
    """Bootstrap helper: create directories if they don't exist.

    This is intentionally separated from config validation
    per convention 02-Config §10.2.
    """
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def _get_required_path(env_name: str) -> Path:
    """Read a required path from environment.

    Raises:
        EnvironmentError: If the variable is not set.
    """
    value = os.getenv(env_name)
    if not value:
        raise OSError(f"Missing required environment variable: {env_name}")
    return Path(value)
