"""DAG: ds_churn_eda

Runs EDA analysis with visualization on ingested data.
Produces an HTML report with charts saved to the reports volume.

Schedule: None (triggered by ds_churn_ingest, parallel with ds_churn_features)
"""
from __future__ import annotations

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from pendulum import datetime
from runtime_config import churn_data_mount, churn_data_volume, db_secret_ref

with DAG(
    dag_id="ds_churn_eda",
    start_date=datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1},
    tags=["ds_churn", "eda", "report"],
    doc_md="""
    ## DS Churn EDA

    Runs exploratory data analysis after ingestion and generates
    an HTML report with visualizations (distributions, correlations,
    outliers, drift, target analysis).

    Triggered in parallel with `ds_churn_features` by `ds_churn_ingest`.
    """,
) as dag:

    volume = churn_data_volume()
    volume_mount = churn_data_mount()
    data_root = volume_mount.mount_path

    run_eda = KubernetesPodOperator(
        task_id="run_eda_k8s",
        name="churn-eda-pod",
        namespace="default",
        image="churn_app:latest",
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
