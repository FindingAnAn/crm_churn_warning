"""PySpark lifetime-as-of writer for large monthly feature jobs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def write_lifetime_asof_tables_with_spark(
    specs: Sequence[dict[str, Any]],
    db_config: dict[str, Any],
    data_start: str,
    logger,
) -> int:
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
    except ImportError as exc:
        raise RuntimeError(
            "FEATURE_ENGINE=pyspark requires pyspark. Install the spark optional dependency "
            "and provide a PostgreSQL JDBC driver on Spark classpath."
        ) from exc

    if not specs:
        return 0

    spark = (
        SparkSession.builder.appName("ds-churn-lifetime-asof")
        .config("spark.sql.shuffle.partitions", str(db_config.get("shuffle_partitions", 64)))
        .getOrCreate()
    )

    jdbc_url = f"jdbc:postgresql://{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
    jdbc_props = {
        "user": db_config["user"],
        "password": db_config["password"],
        "driver": "org.postgresql.Driver",
    }

    source_df = spark.read.jdbc(jdbc_url, "public.cas_customer", properties=jdbc_props)
    computed = 0

    for spec in specs:
        end_date = spec["end_date"]
        table_name = f"data_window.cus_lifetime_{spec['window_size']}m_{spec['start_ym']}_{spec['end_ym']}"
        scoped = source_df.filter((F.col("report_month") >= F.lit(data_start)) & (F.col("report_month") <= F.lit(end_date)))

        result = scoped.groupBy("cms_code_enc").agg(
            F.lit(end_date).cast("date").alias("lifetime_asof_date"),
            F.sum("item_count").cast("long").alias("lifetime_total_items"),
            F.sum("total_fee").cast("long").alias("lifetime_total_revenue"),
            F.sum("weight_kg").cast("double").alias("lifetime_total_weight"),
            F.sum("total_complaint").cast("long").alias("lifetime_total_complaint"),
            _safe_ratio(F.sum("total_fee"), F.sum("item_count")).alias("lifetime_avg_revenue_per_item"),
            _safe_ratio(F.sum("weight_kg"), F.sum("item_count")).alias("lifetime_avg_weight_per_item"),
            F.countDistinct("report_month").cast("int").alias("lifetime_months_active"),
            _safe_ratio(F.sum("delay_count"), F.sum("item_count")).alias("lifetime_pct_delay"),
            _safe_ratio(F.sum("refunded"), F.sum("item_count")).alias("lifetime_pct_refund"),
            _safe_ratio(F.sum("noaccepted"), F.sum("item_count")).alias("lifetime_pct_noaccepted"),
            _safe_ratio(F.sum("lost_order"), F.sum("item_count")).alias("lifetime_pct_lost_order"),
            _safe_ratio(F.sum("total_complaint"), F.sum("item_count")).alias("lifetime_pct_complaint"),
            _safe_ratio(F.sum("item_count") - F.sum("nodone"), F.sum("item_count")).alias("lifetime_pct_successful_item"),
            _safe_ratio(
                F.sum(F.when(F.col("delay_count") > 0, F.col("delay_day")).otherwise(0)),
                F.sum(F.when(F.col("delay_count") > 0, 1).otherwise(0)),
            ).alias("lifetime_avg_delayday"),
            F.avg("order_score").cast("double").alias("lifetime_avg_order_score"),
            F.avg("satisfaction_score").cast("double").alias("lifetime_avg_satisfaction"),
            _safe_ratio(F.sum("international"), F.sum("item_count")).alias("lifetime_pct_international"),
            _safe_ratio(F.sum(F.when(F.col("intra_province") == 1, 1).otherwise(0)), F.sum("item_count")).alias(
                "lifetime_pct_intra_province"
            ),
        )

        result.write.jdbc(jdbc_url, table_name, mode="overwrite", properties=jdbc_props)
        logger.info("Spark wrote %s", table_name)
        computed += 1

    spark.stop()
    return computed


def _safe_ratio(numerator, denominator):
    from pyspark.sql import functions as F

    return F.when(denominator == 0, F.lit(0.0)).otherwise(numerator.cast("double") / denominator.cast("double"))
