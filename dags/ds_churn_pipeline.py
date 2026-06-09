"""Weekly churn model pipeline DAG."""
from __future__ import annotations

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from pendulum import datetime
from runtime_config import churn_data_mount, churn_data_volume, db_secret_ref, get_setting

with DAG(
    dag_id="ds_churn_pipeline",
    start_date=datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    schedule=get_setting("CHURN_MODEL_SCHEDULE", "0 5 * * 6"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
    tags=["ds_churn", "pipeline", "model", "k8s"],
    doc_md="""
    ## DS Churn Pipeline

    Runs the full churn training and scoring pipeline every week at 05:00.
    """,
) as dag:
    volume = churn_data_volume()
    volume_mount = churn_data_mount()
    data_root = volume_mount.mount_path

    run_pipeline = KubernetesPodOperator(
        task_id="run_churn_pipeline",
        name="churn-pipeline-pod",
        namespace="default",
        image="churn_app:latest",
        image_pull_policy="IfNotPresent",
        cmds=["python", "-m", "pipelines.churn.cli"],
        env_vars={
            "TZ": "Asia/Ho_Chi_Minh",
            "PYTHONUNBUFFERED": "1",
            "CSKH_FILE_PATH": get_setting(
                "CSKH_FILE_PATH",
                f"{data_root}/cskh/confirmed_churners.csv",
            ),
            "CHURN_MODEL_DIR": get_setting("CHURN_MODEL_DIR", f"{data_root}/models"),
        },
        env_from=db_secret_ref(),
        volumes=[volume],
        volume_mounts=[volume_mount],
        is_delete_operator_pod=True,
        get_logs=True,
    )
