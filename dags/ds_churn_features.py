"""DAG: ds_churn_features

Generates sliding-window features from ingested data.

Schedule: None (triggered by ds_churn_ingest)
"""
from __future__ import annotations

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from pendulum import datetime
from runtime_config import churn_data_mount, churn_data_volume, db_secret_ref, get_setting

with DAG(
    dag_id="ds_churn_features",
    start_date=datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    schedule=None,          # chỉ chạy khi ingest trigger
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1},
    tags=["ds_churn", "features"],
) as dag:
    volume = churn_data_volume()
    volume_mount = churn_data_mount()

    run_features = KubernetesPodOperator(
        task_id="run_features_k8s",
        name="churn-features-pod",
        namespace="default",
        image="churn_app:latest",
        image_pull_policy="IfNotPresent",
        cmds=[
            "python",
            "-m",
            "features.engineering.cli.generate",
            "--start",
            get_setting("FEATURE_START_DATE", "2025-01-01"),
        ],
        env_vars={
            "WINDOW_SCHEMA": "data_window",
            "TZ": "Asia/Ho_Chi_Minh",
            "PYTHONUNBUFFERED": "1",
        },
        env_from=db_secret_ref(),
        volumes=[volume],
        volume_mounts=[volume_mount],
        is_delete_operator_pod=True,
        get_logs=True,
    )

    run_features
