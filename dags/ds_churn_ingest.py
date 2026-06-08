"""DAG: ds_churn_ingest

Scans for new ZIP data files, loads them into the database,
validates data quality, and triggers the features DAG.

Schedule: 09:00 on the 13th and 23rd of every month
"""
from __future__ import annotations

from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from pendulum import datetime

from common import churn_data_mount, churn_data_volume, db_secret_ref

with DAG(
    dag_id="ds_churn_ingest",
    start_date=datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    schedule="0 9 13,23 * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2},
    tags=["ds_churn", "ingest"],
) as dag:
    volume = churn_data_volume()
    volume_mount = churn_data_mount()

    ingest_scan_and_load = KubernetesPodOperator(
        task_id="ingest_scan_and_load_k8s",
        name="churn-ingestion-pod",
        namespace="default",
        image="churn_app:latest",
        image_pull_policy="IfNotPresent",
        cmds=["python", "-m", "data.ingestion.jobs.ingest_zip_job"],
        env_vars={"TZ": "Asia/Ho_Chi_Minh"},
        env_from=db_secret_ref(),
        volumes=[volume],
        volume_mounts=[volume_mount],
        is_delete_operator_pod=True,
        get_logs=True,
    )

    validate_data = KubernetesPodOperator(
        task_id="validate_data_k8s",
        name="churn-ingestion-validate-pod",
        namespace="default",
        image="churn_app:latest",
        image_pull_policy="IfNotPresent",
        cmds=["python", "-m", "data.ingestion.ops.post_ingest_maintenance"],
        env_vars={"TZ": "Asia/Ho_Chi_Minh"},
        env_from=db_secret_ref(),
        volumes=[volume],
        volume_mounts=[volume_mount],
        is_delete_operator_pod=True,
        get_logs=True,
    )

    trigger_features = TriggerDagRunOperator(
        task_id="trigger_features",
        trigger_dag_id="ds_churn_features",
        conf={
            "upstream_run_id": "{{ run_id }}",
            "logical_date": "{{ ds }}",
        },
        wait_for_completion=False,
        reset_dag_run=True,
    )

    trigger_eda = TriggerDagRunOperator(
        task_id="trigger_eda",
        trigger_dag_id="ds_churn_eda",
        conf={
            "upstream_run_id": "{{ run_id }}",
            "logical_date": "{{ ds }}",
        },
        wait_for_completion=False,
        reset_dag_run=True,
    )

    # Flow: Ingest -> Validate -> Trigger Features + EDA in parallel
    ingest_scan_and_load >> validate_data >> [trigger_features, trigger_eda]

