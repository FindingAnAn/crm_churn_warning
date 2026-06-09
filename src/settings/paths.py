"""File system path configuration.

Provides strongly-typed path configuration for data ingestion and model storage.
Separation of config from bootstrap: validation does NOT create directories.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FSConfig:
    """File system paths for the ingestion pipeline.

    Attributes:
        incoming_dir: Directory for new/unprocessed data files.
        saved_dir: Directory for successfully processed data.
        fail_dir: Directory for data that failed validation/processing.
    """

    incoming_dir: Path
    saved_dir: Path
    fail_dir: Path

    @classmethod
    def from_env(cls) -> FSConfig:
        """Load paths from environment variables.

        Required environment variables:
            INCOMING_DIR, SAVED_DIR, FAIL_DIR

        Returns:
            FSConfig instance with paths loaded from environment.

        Raises:
            OSError: If any required path variable is missing.
        """
        return cls(
            incoming_dir=_get_required_path("INCOMING_DIR"),
            saved_dir=_get_required_path("SAVED_DIR"),
            fail_dir=_get_required_path("FAIL_DIR"),
        )

    def validate(self) -> None:
        """Validate that path values are non-empty.

        NOTE: Does NOT check existence or create directories.
              That belongs in bootstrap code (see docs/conventions/02-Config_conventions.md §10.2).
              This method only validates the configuration, not system state.

        Raises:
            ValueError: If any path is empty.
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

    def __repr__(self) -> str:
        """Safe string representation for logging."""
        return (
            f"FSConfig("
            f"incoming_dir={self.incoming_dir!r}, "
            f"saved_dir={self.saved_dir!r}, "
            f"fail_dir={self.fail_dir!r})"
        )


@dataclass(frozen=True)
class ModelPathsConfig:
    """File system paths for the modeling pipeline.

    Attributes:
        model_dir: Root directory for model bundles and artifacts.
        logs_dir: Directory for pipeline logs and output.
    """

    model_dir: Path
    logs_dir: Path

    @classmethod
    def from_env(cls) -> ModelPathsConfig:
        """Load paths from environment variables.

        Environment variables (with safe defaults for local development):
            CHURN_MODEL_DIR: Root for model bundles (default: ./model_bundles)
            LOGS_DIR: Root for logs (default: ./logs)

        Returns:
            ModelPathsConfig instance with values from environment.
        """
        return cls(
            model_dir=Path(os.getenv("CHURN_MODEL_DIR", "./model_bundles")),
            logs_dir=Path(os.getenv("LOGS_DIR", "./logs")),
        )

    def validate(self) -> None:
        """Validate that path values are non-empty.

        NOTE: Does NOT create directories. Use ensure_directories() in bootstrap code.

        Raises:
            ValueError: If any path is empty.
        """
        if not str(self.model_dir).strip():
            raise ValueError("ModelPathsConfig.model_dir must not be empty.")
        if not str(self.logs_dir).strip():
            raise ValueError("ModelPathsConfig.logs_dir must not be empty.")

    def to_safe_dict(self) -> dict[str, str]:
        """Return config as a dict safe for logging."""
        return {
            "model_dir": str(self.model_dir),
            "logs_dir": str(self.logs_dir),
        }

    def __repr__(self) -> str:
        """Safe string representation for logging."""
        return (
            f"ModelPathsConfig("
            f"model_dir={self.model_dir!r}, "
            f"logs_dir={self.logs_dir!r})"
        )


# ── Bootstrap helpers ──────────────────────────────────────────────
def ensure_directories(*paths: Path) -> None:
    """Bootstrap helper: create directories if they don't exist.

    This is intentionally separated from config validation
    per convention docs/conventions/02-Config_conventions.md §10.2.

    Validation checks correctness. Bootstrap/initialization prepares system state.
    They must not be mixed.

    Args:
        *paths: Variable number of Path objects to create.
    """
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


# ── Private helpers ────────────────────────────────────────────────
def _get_required_path(env_var_name: str) -> Path:
    """Helper: Get required path from environment variable.

    Args:
        env_var_name: Name of environment variable.

    Returns:
        Path object from environment.

    Raises:
        OSError: If environment variable is not set or empty.
    """
    value = os.getenv(env_var_name)
    if not value:
        raise OSError(
            f"Required environment variable not set: {env_var_name}. "
            f"Set it in .env or export before running."
        )
    return Path(value)


def _get_required_path(env_name: str) -> Path:
    """Read a required path from environment.

    Raises:
        EnvironmentError: If the variable is not set.
    """
    value = os.getenv(env_name)
    if not value:
        raise OSError(f"Missing required environment variable: {env_name}")
    return Path(value)
