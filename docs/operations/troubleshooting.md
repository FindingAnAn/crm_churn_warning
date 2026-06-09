# Troubleshooting Guide

This runbook covers the common failure modes for the batch churn-warning
pipeline: ingestion, feature generation, monthly modeling, Kubernetes pods, and
monitoring.

## Ingestion

### Cannot Connect To PostgreSQL

- **Signal:** `ingest_data` fails before loading files; logs mention missing
  `PG_*` variables, refused connection, timeout, or authentication failure.
- **Likely cause:** `.env` is missing locally, Kubernetes secret
  `churn-db-secret` is not injected, or `DATABASE_URL`/`PG_HOST` points to the
  wrong database.
- **Fix:** Check `.env.example`, recreate the Kubernetes secret from `.env`, and
  run `python scripts/database/check_db_status.py` before retrying the DAG.

### File Fails Validation

- **Signal:** Ingest logs show schema mismatch, bad header, parse failure, or no
  CSV found after unzip.
- **Likely cause:** Source file format changed, ZIP naming convention changed,
  or the file is incomplete.
- **Fix:** Inspect the copy in the failed-data directory, correct the file at
  source, move the corrected ZIP back to the incoming directory, and trigger
  `ingest_data` again. Do not bypass validation without checking feature SQL
  impact.

### Duplicate Or Replayed ZIP

- **Signal:** A rerun sees a ZIP that was already processed successfully.
- **Fix:** Use `skip_if_logged=True` for reruns that should ignore prior success,
  or clear the relevant `ingest.ingest_log` row only when a controlled reload is
  intended.

## Feature And EDA Jobs

### Feature Table Missing

- **Signal:** Dataset prep cannot load `data_static.cus_lifetime` or
  `data_window.cus_feature_*`.
- **Fix:** Run `build_features` first, then confirm the target tables exist in
  PostgreSQL. If running locally, verify `CHURN_DATA_HOST_PATH`,
  `CHURN_DATA_MOUNT_PATH`, and database credentials in Airflow variables/env.

### EDA Report Has No Temporal Data

- **Signal:** `generate_eda_reports` logs that no window tables were found.
- **Fix:** Build feature windows before running EDA, or run EDA without temporal
  mode for a one-table snapshot.

## Monthly Pipeline

### Guardrail Failed

- **Signal:** `run_churn_pipeline` ends with `guardrail_failed`.
- **Meaning:** The candidate model did not meet minimum F0.5/PR-AUC quality.
- **Fix:** Check `ml_monitor.run_log`, candidate metrics, CSKH label coverage,
  and recent feature drift. If an accepted bundle exists, the system can still
  score with that bundle in normal reject scenarios.

### No CSKH Labels

- **Signal:** Dataset prep logs no confirmed IDs from file or DB.
- **Fix:** Provide `CSKH_DIR` or `CSKH_FILE_PATH`, or ensure a recent prototype
  cache exists if fallback mode is allowed. A first production run needs CSKH
  data to create a reliable prototype.

### Risk List Is Empty

- **Signal:** `data_static.churn_risk_predictions` receives zero rows.
- **Fix:** Check score distribution, `threshold_used`, and
  `CHURN_RISK_THRESHOLD_PCT`. A very strict threshold or degenerate candidate can
  produce no flagged customers.

## Kubernetes And Airflow

### Pod CrashLoopBackOff Or OOMKilled

- **Signal:** Airflow task pod exits repeatedly or Grafana reports memory limit
  exceeded.
- **Fix:** Inspect pod logs, then raise pod memory request/limit for the relevant
  KubernetesPodOperator task. Heavy feature, EDA, and model jobs should run in
  isolated pods rather than the scheduler container.

### Windows HostPath Mount Error

- **Signal:** Kubernetes reports `invalid mode: /churn_data` or fails to create
  a container when mounting a Windows path.
- **Fix:** Use Docker Desktop's Linux-style mount path, for example
  `/run/desktop/mnt/host/d/...`, via `CHURN_DATA_HOST_PATH`.

### Airflow Cannot Read Worker Logs

- **Signal:** Airflow UI reports name resolution errors for a deleted pod.
- **Fix:** Enable Airflow log persistence in Helm values, for example
  `logs.persistence.enabled: true`, so the webserver does not depend on a pod
  that Kubernetes has already removed.

## Monitoring

### Model Drift Warning

- **Signal:** `ml_monitor.score_drift` shows an abnormal risk ratio or
  `ml_monitor.feature_drift` shows high PSI/KS.
- **Fix:** Validate the latest ingest batch, compare feature drift rows against
  the accepted bundle profile, and rerun the monthly pipeline only after the
  data issue is understood.

### Grafana Shows No Container-Level CPU/Memory Locally

- **Signal:** Kubernetes dashboard panels show limits/quotas but no utilization.
- **Likely cause:** Docker Desktop exposes limited cAdvisor labels.
- **Fix:** Use pod-level PromQL in Explore, such as:

```promql
sum(container_memory_usage_bytes{pod=~"churn-.*"}) by (pod)
```

```promql
sum(irate(container_cpu_usage_seconds_total{namespace="default"}[5m])) by (pod)
```
