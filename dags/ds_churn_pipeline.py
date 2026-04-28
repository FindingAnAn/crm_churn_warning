"""
DAG: ds_churn_pipeline
Runs the full churn prediction pipeline v2:
  Dataset Prep (7 steps) → Train → Evaluate → Guardrail
  → Accept/Reject → Save → Score → Export

Schedule: None (triggered by ds_churn_features)
"""
from __future__ import annotations

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s
from pendulum import datetime

with DAG(
    dag_id="ds_churn_pipeline",
    start_date=datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
    tags=["ds_churn", "pipeline", "model", "k8s"],
    doc_md="""
    ## DS Churn Pipeline v2 (Kubernetes Native)

    Runs the full monthly churn prediction pipeline inside an isolated Kubernetes Pod.
    """,
) as dag:

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
            "CSKH_FILE_PATH": "/churn_data/cskh/confirmed_churners.csv",
            "CHURN_MODEL_DIR": "/churn_data/models",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="churn-db-secret"))
        ],
        # Mount host path or PVC to the container for data/models (assuming local HostPath for dev)
        volumes=[
            k8s.V1Volume(
                name="churn-data-mount",
                # prod: path="/data/churn_prediction/ftp_churn"
                host_path=k8s.V1HostPathVolumeSource(path="/run/desktop/mnt/host/d/Churn_Prediction_Product/data")
            )
        ],
        volume_mounts=[
            k8s.V1VolumeMount(
                name="churn-data-mount",
                mount_path="/churn_data",
                sub_path=None,
                read_only=False
            )
        ],
        is_delete_operator_pod=True,
        get_logs=True,
    )
