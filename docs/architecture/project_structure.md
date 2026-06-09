# Project Structure

## Principle

This repo uses a Python `src/` layout. Production code stays under `src/`; Airflow entrypoints stay under `dags/`; deployment assets stay under `infrastructure/`; tests stay under `tests/`.

## Top-Level Layout

```text
crm_churn_warning/
├── dags/                    # Airflow DAGs and DAG-local helpers
├── src/                     # Importable production code
├── tests/                   # Unit and regression tests
├── config/                  # Runtime configuration documentation
├── scripts/                 # Operational entrypoints
├── docs/                    # Architecture, model, API, operations docs
├── infrastructure/
│   ├── docker/              # Dockerfiles and local compose
│   ├── grafana/             # Provisioned dashboards
│   └── helm/                # Helm values
├── data/                    # Local data mount only, ignored by git
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Runtime Boundaries

| Area | Location | Rule |
|---|---|---|
| DAG orchestration | `dags/` | Thin entrypoints. No business logic. |
| Application settings | `src/settings/` | Typed environment-backed settings. |
| Shared infrastructure | `src/core/` | Database and logging primitives. |
| Data ingestion | `src/data/ingestion/` | ZIP scan, validation, DB load. |
| Training dataset | `src/data/preprocessing/training_dataset/` | Time-aware labels, split, weights. |
| Feature generation | `src/features/engineering/` | PostgreSQL/Spark feature build logic. |
| Model training | `src/modeling/training/` | Model fitting only. |
| Model evaluation | `src/modeling/evaluation/` | Metrics, guardrails, accept/reject. |
| Model serving | `src/modeling/serving/` | Batch scoring and risk-table output. |
| Pipeline | `src/pipelines/churn/` | End-to-end application orchestration. |
| Monitoring | `src/monitoring/` | Model quality and drift checks. |
| Deployment | `infrastructure/` | Docker, Helm, Kubernetes config. |

Generated datasets, model bundles, logs, and experiment artifacts are runtime
outputs and are excluded from Git.

## Scheduling

`ds_churn_pipeline` runs weekly at 05:00 by default:

```text
CHURN_MODEL_SCHEDULE="0 5 * * 6"
```

The schedule and Kubernetes data mount paths are runtime settings, not hard-coded constants.

## References

- [Python Packaging User Guide: src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [Cookiecutter Data Science](https://drivendata.github.io/cookiecutter-data-science/)
- [Kedro architecture overview](https://docs.kedro.org/en/stable/getting-started/architecture_overview/)
