# Churn Model Card

## Model Details

- Owner: Data Science / Data Engineering team
- Use case: monthly churn-risk prioritization for CSKH outreach
- Algorithm: XGBoost binary classifier
- Prediction horizon: 2 months
- Production decision rule: accept a candidate only when it passes quality guardrails and improves over the previously accepted bundle
- First-run acceptance rule: `accepted_no_previous`

## Intended Use

The model produces a high-precision risk list for active customers. The output is written to
`data_static.churn_risk_predictions` with churn probability, churn flag, selected threshold, and top reason signals.

This model is for human-assisted retention prioritization. It must not be used to automatically block, penalize, or
downgrade a customer account.

## Dataset Preparation

The dataset pipeline handles limited confirmed churn labels with temporal validation and conservative label logic:

- 2-month prediction horizon.
- Walk-forward window selection with a minimum number of train windows.
- Active and at-risk tiers based on recency thresholds.
- Train-only scaling to avoid leakage.
- Confirmed churn labels from CSKH files or the confirmed-churn table.
- Reliable negatives from recently active customers.
- Prototype-based pseudo churn using Mahalanobis similarity.
- PU-style sample weighting and label smoothing for uncertain groups.

## Accepted Bundle Metadata

Every accepted bundle stores enough metadata to reproduce and audit the scoring run:

- metrics, including PR-AUC and selected threshold
- feature names
- feature importance
- model config
- pipeline config
- training feature profile for future PSI/KS drift checks
- accepted best-config record

The current portfolio narrative should emphasize the high-precision risk list, PR-AUC, threshold selection, and
reproducible bundle metadata rather than a generic dashboard screenshot.

## Monitoring

Model-quality monitoring is stored in PostgreSQL under `ml_monitor`:

- `ml_monitor.run_log`: monthly run status, accepted flag, retrain/score flags, and notes
- `ml_monitor.score_drift`: active count, risk count, score quantiles, risk ratio, and anomaly reason
- `ml_monitor.feature_drift`: feature-level PSI and discrete KS against the accepted training profile
- `ml_monitor.backtest`: precision-in-list once the future label window is available

Infrastructure health is monitored separately with Prometheus and Grafana.

## Known Limits

- The model is batch-oriented, not real-time.
- Labels are delayed and partly incomplete, so PU weighting and pseudo labels are part of the design.
- A rejected candidate may still be used for scoring only when no previous accepted bundle is available.
- Backtest metrics become available only after the future label horizon closes.
