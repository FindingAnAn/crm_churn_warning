# Project Structure

## Principle

This repo uses a Python `src/` layout. Production code stays under `src/`; Airflow entrypoints stay under `dags/`; deployment assets stay under `infrastructure/`; tests stay under `tests/`.

## Top-Level Layout

```text
crm_churn_warning/
├── dags/                    # Airflow DAGs and DAG-local helpers
├── src/                     # Importable production code
├── tests/                   # Unit and regression tests
├── docs/                    # Architecture, model, API, operations docs
├── infrastructure/
│   ├── docker/              # Dockerfiles and local compose
│   └── helm/                # Helm values
├── model_bundles/           # Model artifacts
├── data/                    # Local data mount only, ignored by git
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Runtime Boundaries

| Area | Location | Rule |
|---|---|---|
| DAG orchestration | `dags/` | Thin entrypoints. No business logic. |
| Data ingestion | `src/data/ingestion/` | ZIP scan, validation, DB load. |
| Dataset prep | `src/data/preprocessing/dataset_prep/` | Time-aware labels, split, weights. |
| Feature generation | `src/features/engineering/` | PostgreSQL/Spark feature build logic. |
| Modeling | `src/modeling/` | Train, evaluate, score, export. |
| Monitoring | `src/monitoring/` | Model quality and drift checks. |
| Deployment | `infrastructure/` | Docker, Helm, Kubernetes config. |

## Scheduling

`ds_churn_pipeline` runs weekly at 05:00 by default:

```text
CHURN_MODEL_SCHEDULE="0 5 * * 6"
```

The schedule and Kubernetes data mount paths are runtime settings, not hard-coded constants.
