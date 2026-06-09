"""CLI entrypoint for engineering feature generation."""

import argparse
import os
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in current.parents:
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    raise RuntimeError("Unable to locate repository root")


REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from features.engineering.config.env_loader import load_project_env_files
from features.engineering.pipeline.pipeline import run

try:
    from config.settings import get_config
    _has_config = True
except ImportError:
    _has_config = False


def _to_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_config_value(config_path: str, env_name: str, default_value):
    """Get value from config system or environment variable.
    
    Args:
        config_path: Path in config (e.g., "features.engine")
        env_name: Environment variable name fallback
        default_value: Default value if both missing
        
    Returns:
        The configuration value.
    """
    if _has_config:
        try:
            cfg = get_config()
            value = cfg.get(config_path)
            if value is not None:
                return value
        except Exception:
            pass
    
    # Fall back to environment variable or default
    env_value = os.getenv(env_name)
    return env_value if env_value is not None else default_value


if __name__ == "__main__":
    load_project_env_files()

    month_chunk_default = int(_get_config_value(
        "features.step6_month_chunk",
        "STEP6_MONTH_CHUNK_SIZE",
        2
    ))
    window_chunk_default = int(_get_config_value(
        "features.step6_window_chunk",
        "STEP6_WINDOW_GROUP_SIZE",
        2
    ))
    checkpoint_default = _get_config_value(
        "features.step6_checkpoint",
        "STEP6_CHECKPOINT",
        None
    )
    resume_default = _to_bool(_get_config_value(
        "features.resume_window_step6",
        "RESUME_WINDOW_STEP6",
        "false"
    ))

    parser = argparse.ArgumentParser(description="Generate churn prediction features")
    parser.add_argument("--start", default="2025-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: auto-detect from DB)")
    parser.add_argument("--database-url", default=None, help="Database URL (default: from environment)")
    parser.add_argument("--month-chunk-size", type=int, default=month_chunk_default, help="Step 6 month chunk size (config: features.step6_month_chunk)")
    parser.add_argument("--window-group-size", type=int, default=window_chunk_default, help="Step 6 window-size chunk (config: features.step6_window_chunk)")
    parser.add_argument("--step6-checkpoint", default=checkpoint_default, help="Step 6 checkpoint path (config: features.step6_checkpoint)")
    run(parser.parse_args())

