# Project Review: Churn Warning Batch Pipeline

**Date**: 2026-06-09
**Architecture**: Modular monolith + Airflow on Kubernetes
**Scope**: Monthly batch risk list, not realtime API serving

## Summary

The project is now aligned around one production path: ingest source data, build
time-aware features, prepare a leakage-aware dataset, train/evaluate a candidate
model, accept or reject it, score active customers, export the action list, and
write model-quality monitoring records.

## Strengths

- Clear DAG architecture: `ingest_data`, `build_features`,
  `generate_eda_reports`, `run_churn_pipeline`, and `clean_runtime_files`.
- Dataset preparation avoids major leakage patterns: working set as of
  `window_end`, held-out confirmed churn IDs, historical labels by future
  horizon, and train-only scaling.
- Candidate models are gated by F0.5 and PR-AUC and compared against the prior
  accepted bundle.
- Rejected candidates do not overwrite the accepted bundle; scoring can fall
  back to the accepted model.
- Model-quality monitoring is active in PostgreSQL: run logs, feature drift,
  score drift, and backtest support.
- Infrastructure monitoring remains separated in Prometheus/Grafana.
- Logging setup is centralized in `src/core/logging.py`, while environment
  logging settings live in `src/settings/logging.py`.

## Fixed Issues

- Removed misleading V1/V2 language from the main pipeline story.
- Renamed DAG files away from the redundant `ds_churn_` prefix.
- Replaced fake realtime API docs with a batch output contract.
- Aligned `model_best_config` writes with the actual schema fields.
- Stored the true `threshold_used` after top-risk threshold adjustment.
- Propagated dataset `window_end` and selected `w_star` into monitoring,
  accepted config, and risk export.
- Scoped `USE_TEST_SCHEMA` to one ingest operation to avoid environment leakage
  between runs.

## Remaining Risks

- End-to-end integration tests are still thin for the full monthly pipeline.
- Alert thresholds for PSI, KS, risk-ratio anomalies, and repeated guardrail
  failures should be tuned with production history.
- Feature-selection automation is not implemented; the current feature list is
  configuration-driven and should be reviewed periodically.
- Bundle/version retention and database backup policy should be exercised in an
  operational drill, not only documented.

## Recommended Next Work

1. Add a fixture-backed integration test for dataset prep -> train -> evaluate
   -> score using a tiny synthetic PostgreSQL dataset.
2. Add unit tests for score drift, feature drift, and accept/reject edge cases.
3. Add CI to run compile checks, pytest, lint, and Docker image build.
4. Add production alert rules for failed KPO pods, scheduler restarts, memory
   pressure, guardrail rejects, and abnormal risk ratios.
