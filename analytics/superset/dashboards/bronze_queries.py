"""
Centralized SQL query library for Bronze Pipeline Dashboard.

All queries use Spark SQL syntax and reference Bronze layer tables.
Tables are in the 'bronze' schema with naming convention:
- bronze_trips, bronze_gps_pings, bronze_driver_status, bronze_surge_updates
- bronze_ratings, bronze_payments, bronze_driver_profiles, bronze_rider_profiles
- bronze_dlq (dead letter queue for ingestion errors)

Metadata columns available on all Bronze tables:
- _ingested_at: Timestamp when the record was ingested
- _kafka_partition: Kafka partition number
- _kafka_offset: Kafka offset within the partition
"""

# =============================================================================
# BRONZE PIPELINE DASHBOARD QUERIES (8 queries)
# =============================================================================

# Total events ingested across all topics in last 24 hours
TOTAL_EVENTS_24H = """
SELECT SUM(event_count) as count
FROM (
    SELECT COUNT(*) as event_count FROM bronze.bronze_trips
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT COUNT(*) as event_count FROM bronze.bronze_gps_pings
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT COUNT(*) as event_count FROM bronze.bronze_driver_status
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT COUNT(*) as event_count FROM bronze.bronze_surge_updates
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT COUNT(*) as event_count FROM bronze.bronze_ratings
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT COUNT(*) as event_count FROM bronze.bronze_payments
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT COUNT(*) as event_count FROM bronze.bronze_driver_profiles
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT COUNT(*) as event_count FROM bronze.bronze_rider_profiles
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
) topic_counts
"""

# Event distribution by Kafka topic (last 24 hours)
EVENTS_BY_TOPIC = """
SELECT topic, event_count
FROM (
    SELECT 'trips' as topic, COUNT(*) as event_count FROM bronze.bronze_trips
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT 'gps_pings' as topic, COUNT(*) as event_count FROM bronze.bronze_gps_pings
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT 'driver_status' as topic, COUNT(*) as event_count FROM bronze.bronze_driver_status
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT 'surge_updates' as topic, COUNT(*) as event_count FROM bronze.bronze_surge_updates
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT 'ratings' as topic, COUNT(*) as event_count FROM bronze.bronze_ratings
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT 'payments' as topic, COUNT(*) as event_count FROM bronze.bronze_payments
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT 'driver_profiles' as topic, COUNT(*) as event_count FROM bronze.bronze_driver_profiles
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    UNION ALL
    SELECT 'rider_profiles' as topic, COUNT(*) as event_count FROM bronze.bronze_rider_profiles
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
) topic_counts
ORDER BY event_count DESC
"""

# Ingestion rate per hour (time series, last 24 hours)
INGESTION_RATE_HOURLY = """
SELECT hour, SUM(event_count) as event_count
FROM (
    SELECT DATE_TRUNC('hour', _ingested_at) as hour, COUNT(*) as event_count
    FROM bronze.bronze_trips
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY DATE_TRUNC('hour', _ingested_at)
    UNION ALL
    SELECT DATE_TRUNC('hour', _ingested_at) as hour, COUNT(*) as event_count
    FROM bronze.bronze_gps_pings
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY DATE_TRUNC('hour', _ingested_at)
    UNION ALL
    SELECT DATE_TRUNC('hour', _ingested_at) as hour, COUNT(*) as event_count
    FROM bronze.bronze_driver_status
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY DATE_TRUNC('hour', _ingested_at)
    UNION ALL
    SELECT DATE_TRUNC('hour', _ingested_at) as hour, COUNT(*) as event_count
    FROM bronze.bronze_surge_updates
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY DATE_TRUNC('hour', _ingested_at)
    UNION ALL
    SELECT DATE_TRUNC('hour', _ingested_at) as hour, COUNT(*) as event_count
    FROM bronze.bronze_ratings
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY DATE_TRUNC('hour', _ingested_at)
    UNION ALL
    SELECT DATE_TRUNC('hour', _ingested_at) as hour, COUNT(*) as event_count
    FROM bronze.bronze_payments
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY DATE_TRUNC('hour', _ingested_at)
    UNION ALL
    SELECT DATE_TRUNC('hour', _ingested_at) as hour, COUNT(*) as event_count
    FROM bronze.bronze_driver_profiles
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY DATE_TRUNC('hour', _ingested_at)
    UNION ALL
    SELECT DATE_TRUNC('hour', _ingested_at) as hour, COUNT(*) as event_count
    FROM bronze.bronze_rider_profiles
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY DATE_TRUNC('hour', _ingested_at)
) hourly_counts
GROUP BY hour
ORDER BY hour
"""

# Total DLQ errors (last 24 hours)
DLQ_ERROR_COUNT = """
SELECT COALESCE(COUNT(*), 0) as count
FROM bronze.bronze_dlq
WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
"""

# DLQ errors by error type
DLQ_ERRORS_BY_TYPE = """
SELECT
    COALESCE(error_type, 'unknown') as error_type,
    COUNT(*) as count
FROM bronze.bronze_dlq
WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
GROUP BY error_type
ORDER BY count DESC
"""

# Event count by Kafka partition (shows distribution across partitions)
PARTITION_DISTRIBUTION = """
SELECT partition_id, SUM(event_count) as event_count
FROM (
    SELECT _kafka_partition as partition_id, COUNT(*) as event_count
    FROM bronze.bronze_trips
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY _kafka_partition
    UNION ALL
    SELECT _kafka_partition as partition_id, COUNT(*) as event_count
    FROM bronze.bronze_gps_pings
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY _kafka_partition
    UNION ALL
    SELECT _kafka_partition as partition_id, COUNT(*) as event_count
    FROM bronze.bronze_driver_status
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY _kafka_partition
    UNION ALL
    SELECT _kafka_partition as partition_id, COUNT(*) as event_count
    FROM bronze.bronze_surge_updates
    WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
    GROUP BY _kafka_partition
) partition_counts
GROUP BY partition_id
ORDER BY partition_id
"""

# Latest ingestion timestamp per topic (data freshness)
LATEST_INGESTION = """
SELECT topic, latest_ingestion
FROM (
    SELECT 'trips' as topic, MAX(_ingested_at) as latest_ingestion FROM bronze.bronze_trips
    UNION ALL
    SELECT 'gps_pings' as topic, MAX(_ingested_at) as latest_ingestion FROM bronze.bronze_gps_pings
    UNION ALL
    SELECT 'driver_status' as topic, MAX(_ingested_at) as latest_ingestion FROM bronze.bronze_driver_status
    UNION ALL
    SELECT 'surge_updates' as topic, MAX(_ingested_at) as latest_ingestion FROM bronze.bronze_surge_updates
    UNION ALL
    SELECT 'ratings' as topic, MAX(_ingested_at) as latest_ingestion FROM bronze.bronze_ratings
    UNION ALL
    SELECT 'payments' as topic, MAX(_ingested_at) as latest_ingestion FROM bronze.bronze_payments
    UNION ALL
    SELECT 'driver_profiles' as topic, MAX(_ingested_at) as latest_ingestion FROM bronze.bronze_driver_profiles
    UNION ALL
    SELECT 'rider_profiles' as topic, MAX(_ingested_at) as latest_ingestion FROM bronze.bronze_rider_profiles
) topic_freshness
ORDER BY latest_ingestion DESC
"""

# Maximum ingestion lag (seconds between event timestamp and ingestion timestamp)
# Uses trips table which has reliable timestamp field
INGESTION_LAG = """
SELECT COALESCE(
    MAX(
        UNIX_TIMESTAMP(_ingested_at) - UNIX_TIMESTAMP(timestamp)
    ),
    0
) as max_lag_seconds
FROM bronze.bronze_trips
WHERE _ingested_at >= DATE_SUB(CURRENT_TIMESTAMP(), 1)
  AND timestamp IS NOT NULL
"""


# =============================================================================
# QUERY COLLECTION
# =============================================================================

BRONZE_PIPELINE_QUERIES = {
    "total_events_24h": TOTAL_EVENTS_24H,
    "events_by_topic": EVENTS_BY_TOPIC,
    "ingestion_rate_hourly": INGESTION_RATE_HOURLY,
    "dlq_error_count": DLQ_ERROR_COUNT,
    "dlq_errors_by_type": DLQ_ERRORS_BY_TYPE,
    "partition_distribution": PARTITION_DISTRIBUTION,
    "latest_ingestion": LATEST_INGESTION,
    "ingestion_lag": INGESTION_LAG,
}
