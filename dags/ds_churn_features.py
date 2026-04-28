"""DAG: ds_churn_features

Generates sliding-window features from ingested data and triggers
the downstream pipeline DAG.

Schedule: None (triggered by ds_churn_ingest)
"""
from __future__ import annotations

from airflow import DAG
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s
from pendulum import datetime

with DAG(
    dag_id="ds_churn_features",
    start_date=datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    schedule=None,          # chỉ chạy khi ingest trigger
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1},
    tags=["ds_churn", "features"],
) as dag:

    # Common volume configuration for data access
    volume = k8s.V1Volume(
        name="churn-data-mount",
        # prod: path="/data/churn_prediction/ftp_churn"
        host_path=k8s.V1HostPathVolumeSource(path="/run/desktop/mnt/host/d/Churn_Prediction_Product/data")
    )
    volume_mount = k8s.V1VolumeMount(
        name="churn-data-mount",
        mount_path="/churn_data",
        sub_path=None,
        read_only=False
    )

    run_features = KubernetesPodOperator(
        task_id="run_features_k8s",
        name="churn-features-pod",
        namespace="default",
        image="churn_app:latest",
        image_pull_policy="IfNotPresent",
        cmds=["python", "-m", "features.engineering.feature_gen.run_feature_generation", "--start", "2025-01-01", "--incremental"],
        env_vars={
            "WINDOW_SCHEMA": "data_window",
            "TZ": "Asia/Ho_Chi_Minh",
            "PYTHONUNBUFFERED": "1",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="churn-db-secret"))
        ],
        volumes=[volume],
        volume_mounts=[volume_mount],
        is_delete_operator_pod=True,
        get_logs=True,
    )

    trigger_pipeline = TriggerDagRunOperator(
        task_id="trigger_pipeline",
        trigger_dag_id="ds_churn_pipeline",
        conf={
            "upstream_features_run_id": "{{ run_id }}",
            "logical_date": "{{ ds }}",
        },
        wait_for_completion=False,
        reset_dag_run=True,
    )

    run_features >> trigger_pipeline
