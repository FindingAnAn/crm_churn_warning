"""Unified logging configuration.

Merges:
  - Ingestion/Data_pull/logging_config.py
  - Preprocess/logging_config.py

Conventions applied:
  - 06-Logging §4.7: Log once at boundary.
  - 08-Security §7.1: Never log secrets.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_CONFIGURED = False


def configure_logging(
    logs_dir: str | Path = "./logs",
    app_name: str = "ds-churn",
    level: int = logging.INFO,
) -> None:
    """Configure logging for the entire application.

    Call once at the application entrypoint. Subsequent calls are no-ops
    to prevent duplicate handlers.

    In containerized environments (K8s pods, Docker), file logging is
    automatically disabled if the log directory cannot be created.
    All output goes to stdout/stderr, which is captured by the
    container runtime (Airflow KubernetesPodOperator, ``kubectl logs``).

    Args:
        logs_dir: Directory for log files (will be created if missing).
        app_name: Application name used in log filenames.
        level: Root logging level.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    # ── Determine if file logging is possible ──────────────
    logs_path = Path(logs_dir)
    file_logging_enabled = True
    try:
        logs_path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Container environments often lack write access to the working dir.
        # Gracefully fallback to console-only logging.
        print(
            f"WARNING: No write permission for '{logs_path.resolve()}'. "
            "File logging disabled — using console only."
        )
        file_logging_enabled = False
    except Exception as e:
        print(
            f"WARNING: Could not create log directory '{logs_path}': {e}. "
            "File logging disabled — using console only."
        )
        file_logging_enabled = False

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates on re-import
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # ── Formatters ─────────────────────────────────────────
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_formatter = logging.Formatter(
        fmt="%(levelname)-8s | %(name)-20s | %(message)s",
    )

    # ── Console handler — always enabled ───────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # ── File handler — only if directory is writable ───────
    if file_logging_enabled:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                logs_path / f"{app_name}.log",
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logging.getLogger(__name__).warning(
                "File logging initialization failed: %s. Console only.", e
            )


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance.

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        ``logging.Logger`` instance.
    """
    return logging.getLogger(name)
