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
from runtime_config import churn_data_mount, churn_data_volume, db_secret_ref, get_setting

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
    data_root = volume_mount.mount_path

    run_ingestion = KubernetesPodOperator(
        task_id="scan_and_ingest",
        name="churn-ingestion-pod",
        namespace="default",
        image="churn_app:latest",
        image_pull_policy="IfNotPresent",
        cmds=["python", "-m", "data.ingestion.scanner"],
        env_vars={
            "TZ": "Asia/Ho_Chi_Minh",
            "INCOMING_DIR": get_setting("INCOMING_DIR", f"{data_root}/incoming"),
            "SAVED_DIR": get_setting("SAVED_DIR", f"{data_root}/saved"),
            "FAIL_DIR": get_setting("FAIL_DIR", f"{data_root}/failed"),
        },
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

    run_ingestion >> [trigger_features, trigger_eda]

