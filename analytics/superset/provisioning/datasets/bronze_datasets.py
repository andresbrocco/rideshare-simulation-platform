"""Bronze layer dataset definitions for Superset provisioning.

These datasets query the Bronze layer tables for Data Ingestion Monitoring dashboard.
All datasets use the consolidated pattern with proper column and metric definitions.
"""

from provisioning.dashboards.base import (
    ColumnDefinition,
    DatasetDefinition,
    MetricDefinition,
)


# =============================================================================
# Bronze Layer - CONSOLIDATED DATASETS
# =============================================================================

# Consolidated ingestion events dataset - for all ingestion monitoring charts
BRONZE_INGESTION_EVENTS = DatasetDefinition(
    name="bronze_ingestion_events",
    description="Bronze layer ingestion events with source and timing - consolidated for all ingestion charts",
    sql="""
SELECT
    source,
    _ingested_at,
    DATE_TRUNC('hour', _ingested_at) AS hour_timestamp,
    _kafka_partition,
    _kafka_timestamp,
    CASE
        WHEN _kafka_timestamp IS NOT NULL
        THEN UNIX_TIMESTAMP(_ingested_at) - UNIX_TIMESTAMP(_kafka_timestamp)
        ELSE NULL
    END AS ingestion_delay_seconds
FROM (
    SELECT 'trips' as source, _ingested_at, _kafka_partition, _kafka_timestamp
    FROM bronze.bronze_trips
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'gps_pings' as source, _ingested_at, _kafka_partition, _kafka_timestamp
    FROM bronze.bronze_gps_pings
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'driver_status' as source, _ingested_at, _kafka_partition, _kafka_timestamp
    FROM bronze.bronze_driver_status
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'surge_updates' as source, _ingested_at, _kafka_partition, _kafka_timestamp
    FROM bronze.bronze_surge_updates
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'ratings' as source, _ingested_at, _kafka_partition, _kafka_timestamp
    FROM bronze.bronze_ratings
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'payments' as source, _ingested_at, _kafka_partition, _kafka_timestamp
    FROM bronze.bronze_payments
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'driver_profiles' as source, _ingested_at, _kafka_partition, _kafka_timestamp
    FROM bronze.bronze_driver_profiles
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'rider_profiles' as source, _ingested_at, _kafka_partition, _kafka_timestamp
    FROM bronze.bronze_rider_profiles
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
) events
""",
    columns=(
        ColumnDefinition("source", "VARCHAR", "Source", filterable=True, groupby=True),
        ColumnDefinition(
            "_ingested_at",
            "TIMESTAMP",
            "Ingested At",
            is_dttm=True,
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition(
            "hour_timestamp",
            "TIMESTAMP",
            "Hour",
            is_dttm=True,
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition(
            "_kafka_partition",
            "INTEGER",
            "Partition",
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition(
            "_kafka_timestamp",
            "TIMESTAMP",
            "Kafka Timestamp",
            is_dttm=True,
            filterable=False,
            groupby=False,
        ),
        ColumnDefinition(
            "ingestion_delay_seconds",
            "DOUBLE",
            "Delay (s)",
            filterable=False,
            groupby=False,
        ),
    ),
    metrics=(
        MetricDefinition(
            "count_events",
            "COUNT(*)",
            "Event Count",
            d3format=",d",
        ),
        MetricDefinition(
            "max_delay",
            "MAX(ingestion_delay_seconds)",
            "Max Delay (s)",
            d3format=",.0f",
        ),
        MetricDefinition(
            "avg_delay",
            "AVG(ingestion_delay_seconds)",
            "Avg Delay (s)",
            d3format=",.1f",
        ),
        MetricDefinition(
            "count_partitions",
            "COUNT(DISTINCT _kafka_partition)",
            "Partition Count",
            d3format=",d",
        ),
        MetricDefinition(
            "distinct_sources",
            "COUNT(DISTINCT source)",
            "Active Sources",
            d3format=",d",
        ),
    ),
    main_dttm_col="_ingested_at",
    cache_timeout=60,
)


# Consolidated DLQ dataset - for all DLQ error charts
BRONZE_DLQ_ERRORS = DatasetDefinition(
    name="bronze_dlq_errors",
    description="Dead letter queue errors with type and timing",
    sql="""
SELECT
    _ingested_at,
    DATE_TRUNC('hour', _ingested_at) AS hour_timestamp,
    COALESCE(error_type, 'unknown') as error_type,
    kafka_topic,
    error_message
FROM bronze.bronze_dlq
WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
  AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
""",
    columns=(
        ColumnDefinition(
            "_ingested_at",
            "TIMESTAMP",
            "Ingested At",
            is_dttm=True,
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition(
            "hour_timestamp",
            "TIMESTAMP",
            "Hour",
            is_dttm=True,
            filterable=True,
            groupby=True,
        ),
        ColumnDefinition("error_type", "VARCHAR", "Error Type", filterable=True, groupby=True),
        ColumnDefinition("kafka_topic", "VARCHAR", "Kafka Topic", filterable=True, groupby=True),
        ColumnDefinition(
            "error_message", "VARCHAR", "Error Message", filterable=False, groupby=False
        ),
    ),
    metrics=(
        MetricDefinition(
            "count_errors",
            "COUNT(*)",
            "Error Count",
            d3format=",d",
        ),
        MetricDefinition(
            "count_error_types",
            "COUNT(DISTINCT error_type)",
            "Error Types",
            d3format=",d",
        ),
    ),
    main_dttm_col="_ingested_at",
    cache_timeout=60,
)


# =============================================================================
# All Bronze Datasets
# =============================================================================

BRONZE_DATASETS: tuple[DatasetDefinition, ...] = (
    BRONZE_INGESTION_EVENTS,
    BRONZE_DLQ_ERRORS,
)
