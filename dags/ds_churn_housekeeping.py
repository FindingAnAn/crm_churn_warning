"""
DAG: ds_churn_housekeeping
Dọn dẹp định kỳ các runtime folders
Schedule: 03:00 hàng ngày
"""
from __future__ import annotations

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s
from pendulum import datetime

# Housekeeping script nội dung
HOUSEKEEPING_SCRIPT = '''
#!/bin/bash
set -e

# Configuration
BUNDLE_KEEP_COUNT=${BUNDLE_KEEP_COUNT:-10}
LOG_RETENTION_DAYS=${LOG_RETENTION_DAYS:-30}
SAVED_RETENTION_DAYS=${SAVED_RETENTION_DAYS:-90}
FAIL_RETENTION_DAYS=${FAIL_RETENTION_DAYS:-30}
INCOMING_RETENTION_DAYS=${INCOMING_RETENTION_DAYS:-7}

# CÁC ĐƯỜNG DẪN CHUẨN TRONG DOCKER CONTAINER
BUNDLE_DIR="${CHURN_MODEL_DIR}/bundles"
LOG_DIR="/opt/airflow/logs"
DATA_ROOT="/churn_data"

echo "=== DS_CHURN Housekeeping - $(date) ==="

# 1. Bundle retention
echo "[1] Cleaning old bundles at: ${BUNDLE_DIR}"
if [[ -d "${BUNDLE_DIR}" ]]; then
    # Đếm số lượng folder (mỗi bundle là 1 folder)
    bundle_count=$(find "${BUNDLE_DIR}" -maxdepth 1 -type d ! -path "${BUNDLE_DIR}" | wc -l)

    if [[ ${bundle_count} -gt ${BUNDLE_KEEP_COUNT} ]]; then
        echo "   Found ${bundle_count} bundles. Keeping last ${BUNDLE_KEEP_COUNT}..."
        # List theo thời gian sửa đổi -> sort -> lấy các dòng thừa -> xóa
        find "${BUNDLE_DIR}" -maxdepth 1 -type d ! -path "${BUNDLE_DIR}" -printf '%T@ %p\\n' | \
            sort -n | head -n -${BUNDLE_KEEP_COUNT} | cut -d' ' -f2- | xargs -r rm -rf
        echo "   Cleaned old bundles."
    else
        echo "   Bundle count (${bundle_count}) <= limit. Skipping."
    fi
else
    echo "   Warning: Bundle dir ${BUNDLE_DIR} not found!"
fi

# 2. Log rotation (Airflow Logs)
echo "[2] Cleaning old logs at: ${LOG_DIR}"
if [[ -d "${LOG_DIR}" ]]; then
    find "${LOG_DIR}" -type f \\( -name "*.log" -o -name "*.log.*" \\) \\
        -mtime +${LOG_RETENTION_DAYS} -delete 2>/dev/null || true
    find "${LOG_DIR}" -type d -empty -delete 2>/dev/null || true
    echo "   Cleaned logs older than ${LOG_RETENTION_DAYS} days."
fi

# 3. Saved data retention (Data đã xử lý thành công)
# Đường dẫn: /data/saved
SAVED_DIR="${DATA_ROOT}/saved"
echo "[3] Cleaning old saved data at: ${SAVED_DIR}"
if [[ -d "${SAVED_DIR}" ]]; then
    find "${SAVED_DIR}" -type f -mtime +${SAVED_RETENTION_DAYS} -delete 2>/dev/null || true
    find "${SAVED_DIR}" -type d -empty -delete 2>/dev/null || true
    echo "   Cleaned saved data older than ${SAVED_RETENTION_DAYS} days."
fi

# 4. Fail data retention (Data lỗi)
# Đường dẫn: /data/failed
FAIL_DIR="${DATA_ROOT}/failed"
echo "[4] Cleaning old fail data at: ${FAIL_DIR}"
if [[ -d "${FAIL_DIR}" ]]; then
    find "${FAIL_DIR}" -type f -mtime +${FAIL_RETENTION_DAYS} -delete 2>/dev/null || true
    find "${FAIL_DIR}" -type d -empty -delete 2>/dev/null || true
    echo "   Cleaned fail data older than ${FAIL_RETENTION_DAYS} days."
fi

# 5. Incoming data retention (File zip gốc quá cũ chưa ai xử lý?)
# Đường dẫn: /data/incoming
INCOMING_DIR="${DATA_ROOT}/incoming"
echo "[5] Cleaning old incoming data at: ${INCOMING_DIR}"
if [[ -d "${INCOMING_DIR}" ]]; then
    find "${INCOMING_DIR}" -type f -mtime +${INCOMING_RETENTION_DAYS} -delete 2>/dev/null || true
    echo "   Cleaned incoming files older than ${INCOMING_RETENTION_DAYS} days."
fi

echo "=== Housekeeping Complete ==="
'''

with DAG(
    dag_id="ds_churn_housekeeping",
    start_date=datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    schedule="0 3 * * *",  # 03:00 hàng ngày
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
    tags=["ds_churn", "maintenance"],
) as dag:

    # Imports moved to module top per Convention 04 §4.1

    # Note: For logs sweeping, Airflow logs might be on a different PVC (or not needed locally if ephemeral pod)
    # But we mount /churn_data PVC to sweep bundles, saved, failed data.
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

    housekeeping = KubernetesPodOperator(
        task_id="run_housekeeping_k8s",
        name="churn-housekeeping-pod",
        namespace="default",
        image="churn_app:latest",
        image_pull_policy="IfNotPresent",
        cmds=["/bin/bash", "-c", HOUSEKEEPING_SCRIPT],
        env_vars={"CHURN_MODEL_DIR": "/churn_data/models"},
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="churn-db-secret"))
        ],
        volumes=[volume],
        volume_mounts=[volume_mount],
        is_delete_operator_pod=True,
        get_logs=True,
    )
