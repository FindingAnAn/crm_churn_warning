# Batch Output Access Examples

The current system is a monthly batch churn-warning pipeline, not a real-time
HTTP prediction service. Consumers should read the latest action list from
PostgreSQL after the pipeline finishes.

## PostgreSQL

```sql
SELECT
    cms_code_enc,
    churn_probability,
    threshold_used,
    reason_1,
    reason_2,
    reason_3,
    scored_at,
    window_end,
    w_star,
    horizon
FROM data_static.churn_risk_predictions
ORDER BY churn_probability DESC;
```

## Python

```python
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg2://USER:PASSWORD@HOST:5432/DB")

risk_list = pd.read_sql(
    """
    SELECT cms_code_enc, churn_probability, threshold_used, reason_1, reason_2, reason_3
    FROM data_static.churn_risk_predictions
    ORDER BY churn_probability DESC
    """,
    engine,
)

print(risk_list.head(20))
```
