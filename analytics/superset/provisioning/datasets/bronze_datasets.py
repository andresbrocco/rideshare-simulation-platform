"""Bronze layer dataset definitions for Superset provisioning.

These datasets query the Bronze layer tables for Data Ingestion Monitoring dashboard.
"""

from provisioning.dashboards.base import DatasetDefinition


# =============================================================================
# Data Ingestion Monitoring - KPI Datasets
# =============================================================================

BRONZE_TOTAL_EVENTS_24H = DatasetDefinition(
    name="bronze_total_events_24h",
    description="Total events ingested across all Bronze tables in last 24 hours for high-level health check",
    sql="""
SELECT COUNT(*) as total_events
FROM (
    SELECT 1 FROM bronze.bronze_trips
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 1 FROM bronze.bronze_gps_pings
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 1 FROM bronze.bronze_driver_status
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 1 FROM bronze.bronze_surge_updates
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 1 FROM bronze.bronze_ratings
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 1 FROM bronze.bronze_payments
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 1 FROM bronze.bronze_driver_profiles
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 1 FROM bronze.bronze_rider_profiles
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
) events
""",
)

BRONZE_DLQ_ERROR_COUNT = DatasetDefinition(
    name="bronze_dlq_error_count",
    description="Dead letter queue error count in last 24 hours - should be zero in healthy operation",
    sql="""
SELECT COUNT(*) as error_count
FROM bronze.bronze_dlq
WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
  AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
""",
)

BRONZE_MAX_INGESTION_DELAY = DatasetDefinition(
    name="bronze_max_ingestion_delay",
    description="Maximum delay between Kafka message timestamp and Bronze layer ingestion (last 1 hour)",
    sql="""
SELECT
    MAX(UNIX_TIMESTAMP(_ingested_at) - UNIX_TIMESTAMP(_kafka_timestamp)) as max_delay_seconds
FROM bronze.bronze_trips
WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
  AND _ingested_at >= current_timestamp - INTERVAL 1 HOUR
  AND _kafka_timestamp IS NOT NULL
""",
)


# =============================================================================
# Data Ingestion Monitoring - Volume Analysis Datasets
# =============================================================================

BRONZE_EVENTS_BY_SOURCE = DatasetDefinition(
    name="bronze_events_by_source",
    description="Event counts by data source for identifying missing or lagging sources",
    sql="""
SELECT source, COUNT(*) as event_count
FROM (
    SELECT 'trips' as source FROM bronze.bronze_trips
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'gps_pings' as source FROM bronze.bronze_gps_pings
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'driver_status' as source FROM bronze.bronze_driver_status
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'surge_updates' as source FROM bronze.bronze_surge_updates
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'ratings' as source FROM bronze.bronze_ratings
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'payments' as source FROM bronze.bronze_payments
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'driver_profiles' as source FROM bronze.bronze_driver_profiles
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT 'rider_profiles' as source FROM bronze.bronze_rider_profiles
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
) events
GROUP BY source
ORDER BY event_count DESC
""",
)

BRONZE_DLQ_ERRORS_BY_TYPE = DatasetDefinition(
    name="bronze_dlq_errors_by_type",
    description="DLQ errors grouped by error type for diagnosis",
    sql="""
SELECT
    COALESCE(
        get_json_object(_raw_value, '$.error_type'),
        'unknown'
    ) as error_type,
    COUNT(*) as error_count
FROM bronze.bronze_dlq
WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
  AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
GROUP BY COALESCE(get_json_object(_raw_value, '$.error_type'), 'unknown')
ORDER BY error_count DESC
""",
)


# =============================================================================
# Data Ingestion Monitoring - Time Series Datasets
# =============================================================================

BRONZE_INGESTION_RATE_HOURLY = DatasetDefinition(
    name="bronze_ingestion_rate_hourly",
    description="Hourly ingestion volume trend across all sources",
    sql="""
SELECT
    date_trunc('hour', _ingested_at) as hour,
    source,
    COUNT(*) as events
FROM (
    SELECT _ingested_at, 'trips' as source FROM bronze.bronze_trips
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT _ingested_at, 'gps_pings' as source FROM bronze.bronze_gps_pings
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT _ingested_at, 'driver_status' as source FROM bronze.bronze_driver_status
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT _ingested_at, 'surge_updates' as source FROM bronze.bronze_surge_updates
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT _ingested_at, 'ratings' as source FROM bronze.bronze_ratings
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    UNION ALL
    SELECT _ingested_at, 'payments' as source FROM bronze.bronze_payments
        WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
        AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
) events
GROUP BY date_trunc('hour', _ingested_at), source
ORDER BY hour, source
""",
)


# =============================================================================
# Data Ingestion Monitoring - Distribution & Freshness Datasets
# =============================================================================

BRONZE_PARTITION_DISTRIBUTION = DatasetDefinition(
    name="bronze_partition_distribution",
    description="Event distribution across Kafka partitions for trips topic (4 partitions)",
    sql="""
SELECT
    CAST(_kafka_partition AS STRING) as partition,
    COUNT(*) as events
FROM bronze.bronze_trips
WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
  AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
GROUP BY _kafka_partition
ORDER BY _kafka_partition
""",
)

BRONZE_DATA_FRESHNESS_BY_SOURCE = DatasetDefinition(
    name="bronze_data_freshness_by_source",
    description="Latest ingestion timestamp and age per data source for freshness monitoring",
    sql="""
SELECT
    source,
    MAX(_ingested_at) as last_event_at,
    ROUND(
        (UNIX_TIMESTAMP(current_timestamp) - UNIX_TIMESTAMP(MAX(_ingested_at))) / 60,
        1
    ) as minutes_since_last_event
FROM (
    SELECT 'trips' as source, _ingested_at FROM bronze.bronze_trips
        WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
    UNION ALL
    SELECT 'gps_pings' as source, _ingested_at FROM bronze.bronze_gps_pings
        WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
    UNION ALL
    SELECT 'driver_status' as source, _ingested_at FROM bronze.bronze_driver_status
        WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
    UNION ALL
    SELECT 'surge_updates' as source, _ingested_at FROM bronze.bronze_surge_updates
        WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
    UNION ALL
    SELECT 'ratings' as source, _ingested_at FROM bronze.bronze_ratings
        WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
    UNION ALL
    SELECT 'payments' as source, _ingested_at FROM bronze.bronze_payments
        WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
    UNION ALL
    SELECT 'driver_profiles' as source, _ingested_at FROM bronze.bronze_driver_profiles
        WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
    UNION ALL
    SELECT 'rider_profiles' as source, _ingested_at FROM bronze.bronze_rider_profiles
        WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
) events
GROUP BY source
ORDER BY minutes_since_last_event DESC
""",
)


# =============================================================================
# All Bronze Datasets
# =============================================================================

BRONZE_DATASETS: tuple[DatasetDefinition, ...] = (
    BRONZE_TOTAL_EVENTS_24H,
    BRONZE_DLQ_ERROR_COUNT,
    BRONZE_MAX_INGESTION_DELAY,
    BRONZE_EVENTS_BY_SOURCE,
    BRONZE_DLQ_ERRORS_BY_TYPE,
    BRONZE_INGESTION_RATE_HOURLY,
    BRONZE_PARTITION_DISTRIBUTION,
    BRONZE_DATA_FRESHNESS_BY_SOURCE,
)
