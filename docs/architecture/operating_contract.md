# Operating Contract

This document summarizes the production-facing contract for the churn warning project.

## Engineering Standard

The project is a modular monolith packaged as Python modules under `src/`. Heavy jobs run in isolated Kubernetes pods
through Airflow `KubernetesPodOperator`. Monitoring is split by responsibility:

- PostgreSQL `ml_monitor.*` tables track model-output quality.
- Prometheus and Grafana track infrastructure and pod health.

Local deployment mirrors production with Docker images, Helm values, Kubernetes secrets, and a host-mounted churn data
directory.

## DAG Architecture

| Step | DAG | Responsibility | Output |
|---|---|---|---|
| 01 Ingest | `ingest_data` | Scan ZIP files, validate, load source tables, emit Airflow status/XCom context | Raw source tables |
| 02 Features | `build_features` | Build lifetime and sliding-window SQL features | `data_static`, `data_window` feature tables |
| 03 EDA | `generate_eda_reports` | Generate missing, outlier, correlation, class-balance, and temporal drift reports | HTML/EDA artifacts |
| 04 Pipeline | `run_churn_pipeline` | Dataset prep, train, evaluate, accept/reject, score, export | Accepted bundle and risk table |
| 05 Cleanup | `clean_runtime_files` | Clean old bundles, logs, saved files, failed files, and incoming files | Controlled local retention |

The monthly pipeline entrypoint is:

```bash
python -m pipelines.monthly.monthly_cli
```

It delegates to the maintained implementation:

```bash
python -m pipelines.churn.cli
```

## Monthly Pipeline Contract

`run_churn_pipeline()` coordinates eight stages:

| Stage | Code responsibility | Operational value |
|---|---|---|
| Dataset Prep | Build train/eval/predict sets | Same temporal logic every run |
| Train | Fit XGBoost with PU weights | Candidate model bundle |
| Evaluate | Compute F0.5, PR-AUC, threshold | Quality evidence |
| Guardrail | Check model-quality minimums | Blocks degenerate candidates |
| Accept/Reject | Compare against previous accepted bundle | Prevents regression |
| Save Bundle | Persist accepted model and metadata | Reproducible scoring |
| Score | Score active customers | Risk ranking |
| Export | Write `data_static.churn_risk_predictions` | Feeds CSKH action list |

If a candidate fails the gate or loses to the prior bundle, the system can still score with the accepted bundle. If no
accepted bundle exists, it falls back to the current trained model and logs that condition.

## Dataset Preparation

The dataset pipeline is the core modeling layer. It combines:

- 2-month prediction horizon.
- Walk-forward window selection with minimum train windows.
- Active and at-risk tiers using recency thresholds.
- Train-only scaling to avoid leakage.
- Confirmed churners from CSKH files or DB.
- Reliable negatives from recent active customers.
- Prototype-based pseudo churn via Mahalanobis similarity.
- Sample weights and soft labels for uncertain groups.

## Accepted Model Bundle

Accepted bundles store:

- metrics
- selected threshold
- feature names
- feature importance
- model config
- pipeline config
- training feature profile for future PSI/KS checks
- accepted best-config record

The first accepted bundle uses `accepted_no_previous`.

## Observability Proof

Infrastructure checks belong in Prometheus/Grafana:

```promql
kube_pod_status_phase{namespace="default", phase=~"Failed|Pending"} > 0
sum(container_memory_usage_bytes{namespace="default", pod=~"churn-pipeline-.*"}) by (pod)
rate(kube_pod_container_status_restarts_total{namespace="default", container="airflow-scheduler"}[10m]) > 0
```

Model-quality evidence belongs in PostgreSQL:

```sql
select * from ml_monitor.run_log order by started_at desc limit 20;
select * from ml_monitor.score_drift order by created_at desc limit 20;
select * from ml_monitor.feature_drift where is_anomaly order by created_at desc;
select * from ml_monitor.backtest order by created_at desc limit 20;
```

For a public portfolio artifact, recreate the monitoring panel from these queries instead of relying on an authenticated
Grafana screenshot.
