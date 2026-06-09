"""DAG: generate_eda_reports

Runs EDA analysis with visualization on ingested data.
Produces an HTML report with charts saved to the reports volume.

Schedule: None (triggered by ingest_data, parallel with build_features)
"""
from __future__ import annotations

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from pendulum import datetime
from runtime_config import churn_data_mount, churn_data_volume, db_secret_ref, get_setting

with DAG(
    dag_id="generate_eda_reports",
    start_date=datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1},
    tags=["churn", "eda", "report"],
    doc_md="""
    ## Churn EDA

    Runs exploratory data analysis after ingestion and generates
    an HTML report with visualizations (distributions, correlations,
    outliers, drift, target analysis).

    Triggered in parallel with `build_features` by `ingest_data`.
    """,
) as dag:

    volume = churn_data_volume()
    volume_mount = churn_data_mount()
    data_root = volume_mount.mount_path

    run_eda = KubernetesPodOperator(
        task_id="run_eda_k8s",
        name="churn-eda-pod",
        namespace="default",
        image=get_setting("CHURN_APP_IMAGE", "churn_app:latest"),
        image_pull_policy="IfNotPresent",
        cmds=["python", "-m", "data.eda.run_eda"],
        env_vars={
            "TZ": "Asia/Ho_Chi_Minh",
            "PYTHONUNBUFFERED": "1",
            "EDA_TEMPORAL": "true",
            "EDA_TEMPORAL_MONTHS": "6",
            "EDA_VISUALIZE": "true",
            "EDA_REPORT_DIR": f"{data_root}/reports/eda",
        },
        env_from=db_secret_ref(),
        volumes=[volume],
        volume_mounts=[volume_mount],
        is_delete_operator_pod=True,
        get_logs=True,
    )
