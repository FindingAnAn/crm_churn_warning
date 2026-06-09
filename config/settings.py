"""Environment-aware configuration management.

This module provides environment-specific configuration classes that combine
default values (from config.defaults) with environment variable overrides.

Secrets are loaded from environment variables only (never from defaults).
Non-sensitive values use defaults when environment variable is not set.

Usage:
    from config.settings import get_config

    config = get_config(env='development')
    db_host = config.database['host']
    log_level = config.logging['level']
"""

import os
from typing import Any, Dict

from config.defaults import DEVELOPMENT, PRODUCTION, TESTING, DEFAULTS


class Config:
    """Base configuration class."""

    def __init__(self, env: str = "development"):
        """Initialize config with environment-specific defaults.

        Args:
            env: Environment name ('development', 'production', 'testing').
        """
        self.env = env
        self._config = self._get_env_config(env)

    @staticmethod
    def _get_env_config(env: str) -> Dict[str, Any]:
        """Get environment-specific config dictionary.

        Args:
            env: Environment name.

        Returns:
            Config dictionary for the environment.

        Raises:
            ValueError: If env is not recognized.
        """
        env_map = {
            "development": DEVELOPMENT,
            "dev": DEVELOPMENT,
            "production": PRODUCTION,
            "prod": PRODUCTION,
            "testing": TESTING,
            "test": TESTING,
        }
        if env.lower() not in env_map:
            raise ValueError(
                f"Unknown environment: {env}. "
                f"Must be one of: {', '.join(env_map.keys())}"
            )
        return env_map[env.lower()]

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot notation (e.g., 'database.host').

        Args:
            key: Config key in dot notation (e.g., 'database.host').
            default: Default value if key not found.

        Returns:
            Config value or default.
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def __getitem__(self, key: str) -> Any:
        """Get config value using dict-like syntax.

        Args:
            key: Config key (e.g., 'database', 'logging').

        Returns:
            Config section dictionary.
        """
        return self._config.get(key, {})

    def to_dict(self) -> Dict[str, Any]:
        """Return entire config as dictionary.

        Returns:
            Configuration dictionary.
        """
        return self._config.copy()

    def __repr__(self) -> str:
        """String representation of config."""
        return f"Config(env={self.env})"


class DevelopmentConfig(Config):
    """Development environment configuration."""

    def __init__(self):
        super().__init__(env="development")


class ProductionConfig(Config):
    """Production environment configuration."""

    def __init__(self):
        super().__init__(env="production")


class TestingConfig(Config):
    """Testing environment configuration."""

    def __init__(self):
        super().__init__(env="testing")


def get_config(env: str | None = None) -> Config:
    """Get configuration for the specified environment.

    Environment is determined by (in order):
    1. env parameter if provided
    2. ENVIRONMENT environment variable
    3. Default to 'development'

    Args:
        env: Environment name (optional). If None, reads from ENVIRONMENT env var.

    Returns:
        Config instance for the environment.
    """
    if env is None:
        env = os.getenv("ENVIRONMENT", "development")
    return Config(env=env)


# ════════════════════════════════════════════════════════
# Convenience instances
# ════════════════════════════════════════════════════════

config = get_config()  # Auto-detect environment


def get_database_config() -> Dict[str, Any]:
    """Get database configuration from environment variables.

    All database configuration (host, port, db, user, password, DATABASE_URL)
    must be set in .env file for easy customization.

    Required environment variables:
    - PG_HOST: Database server hostname
    - PG_PORT: Database server port
    - PG_DB: Target database name
    - PG_USER: Database username (required, secret)
    - PG_PASSWORD: Database password (required, secret)
    - DATABASE_URL: Full SQLAlchemy connection URL (optional, for convenience)

    Returns:
        Dictionary with complete database configuration.

    Raises:
        OSError: If required environment variables are missing.
    """
    # All values MUST come from environment variables (set in .env)
    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT")
    dbname = os.getenv("PG_DB")
    user = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")
    database_url = os.getenv("DATABASE_URL")

    if not all([host, port, dbname, user, password]):
        missing = []
        if not host:
            missing.append("PG_HOST")
        if not port:
            missing.append("PG_PORT")
        if not dbname:
            missing.append("PG_DB")
        if not user:
            missing.append("PG_USER")
        if not password:
            missing.append("PG_PASSWORD")
        
        raise OSError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them in .env file or export them before running. "
            "See .env.example for template."
        )

    return {
        "host": host,
        "port": int(port),
        "dbname": dbname,
        "user": user,
        "password": password,
        "database_url": database_url,  # Optional, for convenience
    }


def get_file_system_config() -> Dict[str, Any]:
    """Get file system configuration.

    Returns:
        Dictionary with file system paths.
    """
    fs_config = config["file_system"].copy()

    # Override with environment variables if present
    fs_config["incoming_dir"] = os.getenv(
        "INCOMING_DIR", fs_config.get("incoming_dir")
    )
    fs_config["saved_dir"] = os.getenv("SAVED_DIR", fs_config.get("saved_dir"))
    fs_config["fail_dir"] = os.getenv("FAIL_DIR", fs_config.get("fail_dir"))
    fs_config["cskh_dir"] = os.getenv("CSKH_DIR", fs_config.get("cskh_dir"))

    return fs_config


def get_monitoring_config() -> Dict[str, Any]:
    """Get model-quality monitoring configuration.

    Returns:
        Dictionary with PostgreSQL monitoring settings.
    """
    mon_config = config["monitoring"].copy()

    enabled = os.getenv("ENABLE_MODEL_QUALITY_MONITORING")
    if enabled is not None:
        mon_config["enabled"] = enabled.lower() in {"1", "true", "yes", "on"}

    mon_config["schema"] = os.getenv(
        "ML_MONITOR_SCHEMA",
        mon_config.get("schema", "ml_monitor"),
    )
    mon_config["feature_bins"] = int(
        os.getenv("ML_MONITOR_FEATURE_BINS", mon_config.get("feature_bins", 10))
    )
    mon_config["max_features"] = int(
        os.getenv("ML_MONITOR_MAX_FEATURES", mon_config.get("max_features", 200))
    )

    return mon_config
