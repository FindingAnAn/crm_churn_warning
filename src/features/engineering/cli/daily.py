"""Scheduled or manual daily runner for feature generation."""

import sys
from pathlib import Path
from types import SimpleNamespace


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in current.parents:
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    raise RuntimeError("Unable to locate repository root")


REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from features.engineering.pipeline.pipeline import run

if __name__ == "__main__":
    args = SimpleNamespace(
        start="2025-01-01",
        end=None,
        database_url=None,
        disable_window_optimization=False,
        recompute_last_n=2,
    )
    run(args)
