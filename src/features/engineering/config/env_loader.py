"""Shared environment loading helpers for the engineering feature package."""

from __future__ import annotations

import os

from features.engineering.paths import get_engineering_root, get_repo_root

try:
    from config.settings import get_config
    _has_config = True
except ImportError:
    _has_config = False

ENGINEERING_ROOT = get_engineering_root()
REPO_ROOT = get_repo_root()
ENV_FILES = [ENGINEERING_ROOT / ".env", REPO_ROOT / ".env"]


def load_project_env_files() -> None:
    """Load environment variables from .env files (legacy support).
    
    Note: Prefer using config.settings module for new code.
    This function is kept for backward compatibility.
    """
    loaded_values: dict[str, str] = {}
    for file_path in ENV_FILES:
        if not file_path.exists():
            continue

        for raw_line in file_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                loaded_values[key] = value

    for key, value in loaded_values.items():
        os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    """Get required environment variable.
    
    Tries to get from config.settings first, then environment.
    
    Args:
        name: Environment variable name.
        
    Returns:
        The environment variable value.
        
    Raises:
        RuntimeError: If the variable is not set or empty.
    """
    # Try config first if available
    if _has_config:
        try:
            cfg = get_config()
            # Map common config paths
            config_mapping = {
                "FEATURE_ENGINE": "features.engine",
                "BUILD_LIFETIME_ASOF": "features.build_lifetime_asof",
                "FEATURE_START_DATE": "features.feature_start_date",
            }
            if name in config_mapping:
                value = cfg.get(config_mapping[name])
                if value:
                    return str(value)
        except Exception:
            pass
    
    # Fall back to environment
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def parse_bool(name: str) -> bool:
    value = require_env(name).lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value for {name}: {value}")


def parse_bool_default(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value for {name}: {value}")


def parse_int(name: str) -> int:
    return int(require_env(name))


def parse_str_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def parse_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized or normalized in {"none", "null"}:
        return None

    return int(normalized)
