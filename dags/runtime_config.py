"""Runtime configuration shared by Airflow DAG entrypoints."""

from __future__ import annotations

import os

from airflow.models import Variable
from kubernetes.client import models as k8s

from config.settings import get_config


def get_setting(name: str, default: str) -> str:
    """Read Airflow Variable first, then environment, then default.
    
    Resolution order:
    1. Airflow Variable (if set in Airflow web UI)
    2. Environment variable
    3. config/defaults.py (via config.settings.get_config)
    4. Default parameter provided here
    """
    try:
        value = Variable.get(name, default_var=None)
    except Exception:
        value = None
    
    if value:
        return value
    
    # Try environment variable
    env_value = os.getenv(name)
    if env_value:
        return env_value
    
    # Try config defaults
    cfg = get_config()
    try:
        # Map common setting names to config paths
        config_mapping = {
            "CHURN_MODEL_SCHEDULE": "model.model_schedule",
            "CHURN_MODEL_DIR": "model.model_dir",
            "CHURN_DATA_HOST_PATH": "infrastructure.churn_data_host_path",
            "CHURN_DATA_MOUNT_PATH": "infrastructure.churn_data_mount_path",
            "CHURN_DB_SECRET_NAME": "infrastructure.churn_db_secret_name",
            "CSKH_FILE_PATH": "file_system.cskh_dir",
        }
        
        if name in config_mapping:
            config_path = config_mapping[name]
            keys = config_path.split(".")
            value = cfg.get(config_path)
            if value:
                return str(value)
    except Exception:
        pass
    
    # Fall back to default parameter
    return default


def churn_data_volume() -> k8s.V1Volume:
    return k8s.V1Volume(
        name="churn-data-mount",
        host_path=k8s.V1HostPathVolumeSource(
            path=get_setting("CHURN_DATA_HOST_PATH", "/churn_data"),
        ),
    )


def churn_data_mount() -> k8s.V1VolumeMount:
    return k8s.V1VolumeMount(
        name="churn-data-mount",
        mount_path=get_setting("CHURN_DATA_MOUNT_PATH", "/churn_data"),
        read_only=False,
    )


def db_secret_ref() -> list[k8s.V1EnvFromSource]:
    return [
        k8s.V1EnvFromSource(
            secret_ref=k8s.V1SecretEnvSource(
                name=get_setting("CHURN_DB_SECRET_NAME", "churn-db-secret"),
            ),
        )
    ]
