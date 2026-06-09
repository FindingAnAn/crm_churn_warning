"""Single logging setup point for application entrypoints."""

from __future__ import annotations

import json
import logging
import logging.handlers
from pathlib import Path

_CONFIGURED = False


class JsonLogFormatter(logging.Formatter):
    """Minimal JSON formatter for container logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "function": record.funcName,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    logs_dir: str | Path = "./logs",
    app_name: str = "churn-warning",
    level: int = logging.INFO,
    log_format: str = "text",
) -> None:
    """Configure root logging once for the process.

    Settings parsing lives in ``settings.logging``. This module owns only
    handler/formatter setup so scripts and pipelines do not each configure
    their own root handlers.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    logs_path = Path(logs_dir)
    file_logging_enabled = True
    try:
        logs_path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(
            f"WARNING: No write permission for '{logs_path.resolve()}'. "
            "File logging disabled; using console only."
        )
        file_logging_enabled = False
    except Exception as exc:
        print(
            f"WARNING: Could not create log directory '{logs_path}': {exc}. "
            "File logging disabled; using console only."
        )
        file_logging_enabled = False

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if log_format.lower() == "json":
        file_formatter = JsonLogFormatter()
        console_formatter = file_formatter
    else:
        file_formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_formatter = logging.Formatter(
            fmt="%(levelname)-8s | %(name)-20s | %(message)s",
        )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    if file_logging_enabled:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                logs_path / f"{app_name}.log",
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "File logging initialization failed: %s. Console only.", exc
            )


def configure_logging_from_env(app_name: str = "churn-warning") -> None:
    """Configure logging from environment-backed logging settings."""
    from settings.logging import LoggingConfig

    cfg = LoggingConfig.from_env()
    cfg.validate()
    level = getattr(logging, cfg.level.value, logging.INFO)
    configure_logging(
        logs_dir=cfg.logs_dir,
        app_name=app_name,
        level=level,
        log_format=cfg.format.value,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
