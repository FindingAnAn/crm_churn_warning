# Incident Response

This runbook is for P1/P2 incidents in the monthly churn-warning pipeline.

## Severity

- **P1 Critical:** No usable risk list can be produced for the business window,
  or the exported list is known to be materially wrong.
- **P2 Major:** Pipeline is delayed, a candidate is repeatedly rejected, or
  monitoring shows strong drift that may affect the next CSKH list.
- **P3 Minor:** Non-blocking warnings, EDA/reporting issues, or local-only
  infrastructure noise.

## Response Flow

1. **Triage:** Identify the failing DAG/task, latest run ID, `window_end`, and
   whether `data_static.churn_risk_predictions` still contains a usable prior
   list.
2. **Containment:** If a candidate model failed guardrails, keep the accepted
   bundle and do not overwrite bundle metadata. If ingestion is suspect, pause
   downstream feature/model DAGs until the data issue is understood.
3. **Mitigation:** Recreate missing secrets, rebuild failed feature tables, move
   corrected ZIPs back to incoming data, or rerun `run_churn_pipeline` after the
   root cause is fixed.
4. **Recovery:** Confirm `ml_monitor.run_log` shows the final status, the risk
   table has the expected `window_end`, `threshold_used`, `w_star`, and `horizon`,
   and Airflow marks the relevant DAG run successful or intentionally skipped.
5. **Postmortem:** For P1/P2, record root cause, customer/business impact,
   detection gap, permanent fix, and owner/date for follow-up work.

## Useful Checks

```sql
SELECT *
FROM ml_monitor.run_log
ORDER BY started_at DESC
LIMIT 10;
```

```sql
SELECT window_end, horizon, COUNT(*) AS risk_count, MAX(scored_at) AS last_scored_at
FROM data_static.churn_risk_predictions
GROUP BY window_end, horizon
ORDER BY window_end DESC;
```

```sql
SELECT window_end, feature_name, psi, discrete_ks
FROM ml_monitor.feature_drift
ORDER BY window_end DESC, psi DESC
LIMIT 20;
```
