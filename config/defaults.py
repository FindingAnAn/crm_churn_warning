"""Default configuration values for all environments.

This module defines non-sensitive default values for the churn prediction pipeline.
All public configuration (non-secret) should be defined here.

Secrets (passwords, tokens, API keys) are loaded from environment variables only
and are NOT stored in this file. See .env.example for secret references.

Usage:
    from config.defaults import DEFAULTS

    db_host = DEFAULTS['database']['host']
"""

DEFAULTS = {
    # ════════════════════════════════════════════════════════
    # DATABASE CONFIGURATION
    # ════════════════════════════════════════════════════════
    # Note: Specific database config (host, port, dbname, user, password, DATABASE_URL)
    # must be set in .env file for easy customization.
    # This section contains only generic/public database settings.
    "database": {
        # Generic database settings (no host/port/credentials here)
        # All connection details are in .env for easy switching between dev/prod
    },
    
    # ════════════════════════════════════════════════════════
    # FILE SYSTEM PATHS
    # ════════════════════════════════════════════════════════
    "file_system": {
        # Ingestion pipeline paths (must be configured via environment)
        "incoming_dir": "/churn_data/incoming",
        "saved_dir": "/churn_data/saved",
        "fail_dir": "/churn_data/failed",
        "cskh_dir": "/churn_data/cskh_confirm_churn",
    },
    
    # ════════════════════════════════════════════════════════
    # LOGGING CONFIGURATION
    # ════════════════════════════════════════════════════════
    "logging": {
        "level": "INFO",
        "format": "text",  # or "json"
        "logs_dir": "./logs",
        # Log output format (Python logging style)
        "format_string": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        # Output destinations
        "file": True,
        "console": True,
    },
    
    # ════════════════════════════════════════════════════════
    # MODEL CONFIGURATION
    # ════════════════════════════════════════════════════════
    "model": {
        "model_dir": "./model_bundles",
        "model_schedule": "0 5 * * 6",  # Cron: Every Saturday 05:00 UTC
    },
    
    # ════════════════════════════════════════════════════════
    # FEATURE ENGINEERING
    # ════════════════════════════════════════════════════════
    "features": {
        "engine": "postgres",  # or "spark"
        "build_lifetime_asof": True,  # Lifetime aggregates (vs rolling window)
        "feature_start_date": "2025-01-01",  # ISO 8601 format
        # Feature schema settings
        "schema": "data_window",
        "static_schema": "data_static",
        "static_table": "cus_lifetime",
        # Window optimization settings
        "window_sizes_min": 3,
        "window_sizes_max": 0,
        "enable_window_optimization": True,
        "recompute_last_n": 2,
        "keep_window_history": 2,
        # Feature computation
        "enable_static_features": True,
        "static_data_start": "2025-01-01",
        "batch_insert_size": 5,
        "parallel_render": True,
        # Worker/chunk settings for step 6
        "step6_month_chunk": 2,  # Month chunk size
        "step6_window_chunk": 2,  # Window-size chunk
        "step6_checkpoint": None,  # Checkpoint path (null for none)
        # Execution settings
        "max_workers": 4,  # Max parallel workers
        "resume_window_step6": False,  # Resume from checkpoint
    },
    
    # ════════════════════════════════════════════════════════
    # KUBERNETES / INFRASTRUCTURE
    # ════════════════════════════════════════════════════════
    "infrastructure": {
        "churn_data_host_path": "/churn_data",  # Host machine path
        "churn_data_mount_path": "/churn_data",  # Container mount path
        "churn_db_secret_name": "churn-db-secret",  # K8s secret name
    },
    
    # ════════════════════════════════════════════════════════
    # AIRFLOW (Infrastructure-level, separate from app config)
    # ════════════════════════════════════════════════════════
    "airflow": {
        "docker": {
            "airflow_proj_dir": ".",
            "data_dir": "/data/churn_prediction/ftp_churn",
            "env_file_path": ".env",
        },
        "core": {
            "airflow_uid": 50000,
            "airflow_image_name": "apache/airflow:3.1.7",
        },
        "webserver": {
            "webserver_base_url": "https://ai.vnpost.vn/airflow-churn/",
            "webserver_username": "airflow",
            # password is SECRET: _AIRFLOW_WWW_USER_PASSWORD
        },
        "database": {
            "postgres_user": "airflow",
            "postgres_db": "airflow",
            # password is SECRET: POSTGRES_PASSWORD
        },
        "executor": {
            "executor_type": "CeleryExecutor",
            "dags_paused_at_creation": True,
            "load_examples": False,
        },
        "scheduler": {
            "enable_health_check": True,
            "dag_dir_list_interval": 300,
        },
    },
}


# ════════════════════════════════════════════════════════
# Environment-specific configurations
# ════════════════════════════════════════════════════════

DEVELOPMENT = {
    **DEFAULTS,
    # Database config is in .env (not here) for easy customization
    "logging": {
        **DEFAULTS["logging"],
        "level": "DEBUG",  # Verbose logging in development
        "format_string": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": True,
        "console": True,
    },
    "features": {
        **DEFAULTS["features"],
        "parallel_render": False,  # Disable parallel in dev for easier debugging
    },
}

PRODUCTION = {
    **DEFAULTS,
    # Database config is in .env (not here) for easy customization
    "logging": {
        **DEFAULTS["logging"],
        "level": "INFO",
        "format": "json",  # Use JSON format in production
        "format_string": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": True,
        "console": True,
    },
    "features": {
        **DEFAULTS["features"],
        "parallel_render": True,  # Enable parallel rendering in production
    },
}

TESTING = {
    **DEFAULTS,
    "logging": {
        **DEFAULTS["logging"],
        "level": "DEBUG",
        "logs_dir": "./tests/logs",
    },
}
