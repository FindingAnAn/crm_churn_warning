"""Dynamic path helpers for the engineering feature package."""

from __future__ import annotations

import os
from pathlib import Path

ENGINEERING_ROOT = Path(__file__).resolve().parent


def _discover_repo_root() -> Path:
    for candidate in ENGINEERING_ROOT.parents:
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    raise RuntimeError("Unable to locate repository root")


REPO_ROOT = _discover_repo_root()


def get_engineering_root() -> Path:
    """Return the engineering package root directory."""
    return ENGINEERING_ROOT


def get_repo_root() -> Path:
    """Return the repository root directory."""
    return REPO_ROOT


def get_engineering_logs_dir() -> Path:
    """Return the engineering logs directory."""
    return Path(os.getenv("LOGS_DIR", REPO_ROOT / "logs"))


def get_engineering_sql_dir() -> Path:
    """Return the engineering SQL template directory."""
    return ENGINEERING_ROOT / "sql"
