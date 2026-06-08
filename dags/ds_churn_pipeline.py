"""Weekly churn model pipeline DAG."""
from __future__ import annotations

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from pendulum import datetime

from common import churn_data_mount, churn_data_volume, db_secret_ref, get_setting

with DAG(
    dag_id="ds_churn_pipeline",
    start_date=datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    schedule=get_setting("CHURN_MODEL_SCHEDULE", "0 5 * * 6"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
    tags=["ds_churn", "pipeline", "model", "k8s"],
    doc_md="""
    ## DS Churn Pipeline v2 (Kubernetes Native)

    Runs the full monthly churn prediction pipeline inside an isolated Kubernetes Pod.
    """,
) as dag:
    volume = churn_data_volume()
    volume_mount = churn_data_mount()

    run_pipeline = KubernetesPodOperator(
        task_id="run_monthly_v2_k8s_pod",
        name="churn-pipeline-v2-pod",
        namespace="default", # Or the namespace configured for your local K8s
        image="churn_app:latest",
        image_pull_policy="IfNotPresent",
        cmds=["python", "-m", "pipelines.monthly.monthly_v2_cli"],
        env_vars={
            "TZ": "Asia/Ho_Chi_Minh",
            "PYTHONUNBUFFERED": "1",
            "CSKH_FILE_PATH": get_setting("CSKH_FILE_PATH", "/churn_data/cskh/confirmed_churners.csv"),
            "CHURN_MODEL_DIR": get_setting("CHURN_MODEL_DIR", "/churn_data/models"),
        },
        env_from=db_secret_ref(),
        volumes=[volume],
        volume_mounts=[volume_mount],
        is_delete_operator_pod=True,
        get_logs=True,
    )
