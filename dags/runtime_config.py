"""Runtime configuration shared by Airflow DAG entrypoints."""

from __future__ import annotations

import os

from airflow.models import Variable
from kubernetes.client import models as k8s


def get_setting(name: str, default: str) -> str:
    """Read Airflow Variable first, then environment, then default."""
    try:
        value = Variable.get(name, default_var=None)
    except Exception:
        value = None
    return value or os.getenv(name, default)


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
