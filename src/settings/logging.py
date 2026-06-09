"""Logging configuration.

Defines structured logging setup with level, format, and output paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class LogLevel(str, Enum):
    """Standard Python logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Log output format."""

    TEXT = "text"
    JSON = "json"


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration.

    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        format: Output format (text for humans, json for machines).
        logs_dir: Directory for log files.
    """

    level: LogLevel
    format: LogFormat
    logs_dir: Path

    @classmethod
    def from_env(cls) -> LoggingConfig:
        """Load logging config from environment variables.

        Environment Variables:
            LOG_LEVEL: Logging level (default: INFO)
            LOG_FORMAT: Output format (default: text)
            LOGS_DIR: Directory for logs (default: ./logs)

        Returns:
            Validated LoggingConfig instance.
        """
        level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        try:
            level = LogLevel[level_str]
        except KeyError:
            raise ValueError(
                f"Invalid LOG_LEVEL: {level_str}. "
                f"Must be one of: {', '.join(e.value for e in LogLevel)}"
            )

        format_str = os.getenv("LOG_FORMAT", "text").lower()
        try:
            format_enum = LogFormat[format_str.upper()]
        except KeyError:
            raise ValueError(
                f"Invalid LOG_FORMAT: {format_str}. "
                f"Must be one of: {', '.join(e.value for e in LogFormat)}"
            )

        return cls(
            level=level,
            format=format_enum,
            logs_dir=Path(os.getenv("LOGS_DIR", "./logs")),
        )

    def validate(self) -> None:
        """Validate logging config without side effects.

        Raises:
            ValueError: If any field is invalid.
        """
        if not self.level:
            raise ValueError("LoggingConfig.level must not be empty.")
        if not self.format:
            raise ValueError("LoggingConfig.format must not be empty.")
        if not str(self.logs_dir).strip():
            raise ValueError("LoggingConfig.logs_dir must not be empty.")

    def to_safe_dict(self) -> dict[str, str]:
        """Return config as a dict safe for logging."""
        return {
            "level": self.level.value,
            "format": self.format.value,
            "logs_dir": str(self.logs_dir),
        }

    def __repr__(self) -> str:
        """Safe representation for logging."""
        return (
            f"LoggingConfig(level={self.level.value}, "
            f"format={self.format.value}, logs_dir={self.logs_dir})"
        )
