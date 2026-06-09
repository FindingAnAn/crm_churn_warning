# Performance Reports

This project does not hard-code a static performance report because every
monthly run may accept or reject a candidate model. The authoritative metrics
are stored with the accepted bundle and in PostgreSQL monitoring/config tables.

## Primary Metrics

| Metric | Source | Purpose |
|---|---|---|
| F0.5 | `data_static.model_best_config.metric_f2_val` and bundle metadata | Precision-focused accept/reject metric |
| PR-AUC | `data_static.model_best_config.metric_roc_auc_val` and bundle metadata | Ranking quality under class imbalance |
| Threshold | `best_threshold` and risk table `threshold_used` | Cutoff selected during evaluation and adjusted for risk-list size |
| Risk ratio | `ml_monitor.score_drift.risk_ratio` | Detect abnormal list-size changes |
| Feature PSI/KS | `ml_monitor.feature_drift` | Detect feature distribution drift |

## Report Query

```sql
SELECT
    as_of_month,
    horizon,
    best_k,
    best_threshold,
    metric_f2_val AS f05,
    metric_roc_auc_val AS pr_auc,
    is_accepted,
    accept_rule,
    accepted_at,
    notes
FROM data_static.model_best_config
ORDER BY as_of_month DESC, horizon;
```

## Confusion Matrix

Confusion-matrix style reporting should be generated only when a future label
window has closed. Until then, use PR-AUC/F0.5 on the held-out confirmed set and
precision-in-list backtests from `ml_monitor.backtest`.

## Feature Importance

Accepted bundles store XGBoost gain-based feature importance. Use the bundle
metadata for portfolio/model-card snapshots, and avoid manually copying stale
feature rankings into this document.

## Error Analysis

When backtest labels become available, compare false positives and false
negatives by recency tier, service mix, revenue band, and complaint/satisfaction
signals. Record findings in a dated report rather than editing this contract
file with one-off numbers.
