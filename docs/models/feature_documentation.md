# Feature Documentation

The production feature set is defined in
`src/data/preprocessing/training_dataset/pipeline_config.py` as
`NUMERIC_FEATURES`. Dataset preparation keeps only columns present in the active
feature table and rejects feature names that look like targets, labels, churn
outcomes, future windows, or horizon-derived values.

## Feature Groups

| Group | Examples | Business Meaning | Window |
|---|---|---|---|
| Volume | `item_sum`, `item_avg`, `frequency` | Shipping activity and customer usage intensity | Selected `W*` window and lifetime |
| Revenue | `revenue_sum`, `revenue_avg`, `monetary`, `avg_revenue_per_item` | Customer value and spend pattern | Selected `W*` window and lifetime |
| Reliability | `pct_delay`, `avg_delayday`, `pct_refund`, `pct_noaccepted`, `pct_lost_order` | Service issues that may precede churn | Selected `W*` window |
| Complaint and satisfaction | `complaint_sum`, `complaint_avg`, `pct_complaint`, `satisfaction_avg`, `satisfy_slope` | Explicit dissatisfaction signals | Selected `W*` window |
| Trend and volatility | `item_slope`, `revenue_slope`, `cv_item`, `cv_revenue`, `item_range`, `revenue_range` | Decline or instability in customer behavior | Historical window |
| Service mix | `service_types_used`, `dominant_service_ratio`, `ser_*_sum` | Product/service diversity and concentration | Selected `W*` window |
| Recency and activity | `recency`, `active_months`, `inactive_months`, `active_days`, `inactive_days` | Recent engagement and account inactivity | As of `window_end` |
| EWMA signals | `ewma_item`, `delta_ewma_item`, `ewma_revenue`, `delta_ewma_revenue`, etc. | Smoothed leading indicators and momentum | Walk-forward selected window |

## Missing Values

Feature matrices fill missing numeric values with `0` before scaling. This is
intentional because missing customer activity in a monthly aggregate generally
means no observed activity for that feature/window. The scaler is fit on train
rows only, then applied to eval and predict rows.

## Outliers

The current code does not apply a separate cap/clip step in dataset preparation.
Outlier monitoring belongs to EDA reports and feature drift checks. If clipping
is added later, it must be fit on train data only and stored in the accepted
bundle metadata with the scaler.

## Leakage Guard

The dataset builder rejects feature names containing target-like keywords such
as `label`, `target`, `churn`, `future`, `item_in_horizon`, and
`rev_in_horizon`. Confirmed eval IDs are held out from training and prototype
construction.
