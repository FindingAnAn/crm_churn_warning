"""Configuration package for Churn Warning pipeline.

This package provides environment-aware configuration management.

Quick start:
    from config.settings import get_config
    
    config = get_config()
    db_cfg = config['database']
    
Or use convenience getters:
    from config.settings import get_database_config, get_file_system_config
    
    db = get_database_config()
    fs = get_file_system_config()

Or load all settings together (legacy compatibility):
    from src.settings import get_settings
    
    all_settings = get_settings()
"""

from config.defaults import DEFAULTS, DEVELOPMENT, PRODUCTION, TESTING
from config.settings import (
    Config,
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    config,
    get_config,
    get_database_config,
    get_file_system_config,
    get_monitoring_config,
)

__all__ = [
    "Config",
    "DevelopmentConfig",
    "ProductionConfig",
    "TestingConfig",
    "config",
    "get_config",
    "get_database_config",
    "get_file_system_config",
    "get_monitoring_config",
    "DEFAULTS",
    "DEVELOPMENT",
    "PRODUCTION",
    "TESTING",
]
