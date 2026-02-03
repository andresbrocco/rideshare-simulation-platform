"""Data Ingestion Monitoring Dashboard (Bronze layer).

Monitors:
- Kafka topic ingestion rates
- Dead letter queue errors
- Ingestion lag and freshness
- Partition distribution
"""

from provisioning.dashboards.base import (
    ChartDefinition,
    DashboardDefinition,
    DatasetDefinition,
)

# =============================================================================
# Dataset Definitions
# =============================================================================

TOTAL_EVENTS_24H = DatasetDefinition(
    name="bronze_total_events_24h",
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
    ) events
    """,
    description="Total events ingested across all topics in last 24 hours",
)

EVENTS_BY_TOPIC = DatasetDefinition(
    name="bronze_events_by_topic",
    sql="""
    SELECT topic, COUNT(*) as event_count
    FROM (
        SELECT 'trips' as topic FROM bronze.bronze_trips
            WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
        UNION ALL
        SELECT 'gps_pings' as topic FROM bronze.bronze_gps_pings
            WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
        UNION ALL
        SELECT 'driver_status' as topic FROM bronze.bronze_driver_status
            WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
        UNION ALL
        SELECT 'surge_updates' as topic FROM bronze.bronze_surge_updates
            WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
        UNION ALL
        SELECT 'ratings' as topic FROM bronze.bronze_ratings
            WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
        UNION ALL
        SELECT 'payments' as topic FROM bronze.bronze_payments
            WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    ) events
    GROUP BY topic
    ORDER BY event_count DESC
    """,
    description="Event distribution by Kafka topic",
)

INGESTION_RATE_HOURLY = DatasetDefinition(
    name="bronze_ingestion_rate_hourly",
    sql="""
    SELECT
        date_trunc('hour', _ingested_at) as hour,
        COUNT(*) as events
    FROM (
        SELECT _ingested_at FROM bronze.bronze_trips
            WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
        UNION ALL
        SELECT _ingested_at FROM bronze.bronze_gps_pings
            WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
        UNION ALL
        SELECT _ingested_at FROM bronze.bronze_driver_status
            WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    ) events
    GROUP BY date_trunc('hour', _ingested_at)
    ORDER BY hour
    """,
    description="Hourly ingestion rate time series",
)

DLQ_ERROR_COUNT = DatasetDefinition(
    name="bronze_dlq_error_count",
    sql="""
    SELECT COUNT(*) as error_count
    FROM bronze.bronze_dlq
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    """,
    description="Dead letter queue error count (24h)",
)

DLQ_ERRORS_BY_TYPE = DatasetDefinition(
    name="bronze_dlq_errors_by_type",
    sql="""
    SELECT
        COALESCE(error_type, 'unknown') as error_type,
        COUNT(*) as error_count
    FROM bronze.bronze_dlq
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    GROUP BY COALESCE(error_type, 'unknown')
    ORDER BY error_count DESC
    """,
    description="DLQ errors grouped by error type",
)

PARTITION_DISTRIBUTION = DatasetDefinition(
    name="bronze_partition_distribution",
    sql="""
    SELECT
        _kafka_partition as partition,
        COUNT(*) as events
    FROM bronze.bronze_trips
    WHERE _ingestion_date >= date_format(current_timestamp - INTERVAL 2 DAYS, 'yyyy-MM-dd')
      AND _ingested_at >= current_timestamp - INTERVAL 24 HOURS
    GROUP BY _kafka_partition
    ORDER BY partition
    """,
    description="Events per Kafka partition",
)

LATEST_INGESTION = DatasetDefinition(
    name="bronze_latest_ingestion",
    sql="""
    SELECT topic, MAX(_ingested_at) as latest_ingestion
    FROM (
        SELECT 'trips' as topic, _ingested_at FROM bronze.bronze_trips
            WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
        UNION ALL
        SELECT 'gps_pings' as topic, _ingested_at FROM bronze.bronze_gps_pings
            WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
        UNION ALL
        SELECT 'driver_status' as topic, _ingested_at FROM bronze.bronze_driver_status
            WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
        UNION ALL
        SELECT 'surge_updates' as topic, _ingested_at FROM bronze.bronze_surge_updates
            WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
        UNION ALL
        SELECT 'ratings' as topic, _ingested_at FROM bronze.bronze_ratings
            WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
        UNION ALL
        SELECT 'payments' as topic, _ingested_at FROM bronze.bronze_payments
            WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
    ) events
    GROUP BY topic
    ORDER BY latest_ingestion DESC
    """,
    description="Latest ingestion timestamp per topic",
)

INGESTION_LAG = DatasetDefinition(
    name="bronze_ingestion_lag",
    sql="""
    SELECT
        topic,
        MAX(UNIX_TIMESTAMP(_ingested_at) - UNIX_TIMESTAMP(_kafka_timestamp)) as max_lag_seconds
    FROM (
        SELECT 'trips' as topic, _ingested_at, _kafka_timestamp FROM bronze.bronze_trips
            WHERE _ingestion_date = date_format(current_date, 'yyyy-MM-dd')
            AND _ingested_at >= current_timestamp - INTERVAL 1 HOUR
    ) events
    GROUP BY topic
    ORDER BY max_lag_seconds DESC
    """,
    description="Max lag between Kafka timestamp and ingestion time",
)

# =============================================================================
# Chart Definitions
# =============================================================================

CHARTS: tuple[ChartDefinition, ...] = (
    ChartDefinition(
        name="Total Events (24h)",
        dataset_name="bronze_total_events_24h",
        viz_type="big_number_total",
        metrics=("total_events",),
        layout=(0, 0, 3, 3),
    ),
    ChartDefinition(
        name="DLQ Errors (24h)",
        dataset_name="bronze_dlq_error_count",
        viz_type="big_number_total",
        metrics=("error_count",),
        layout=(0, 3, 3, 3),
        extra_params={"color_picker": {"r": 255, "g": 0, "b": 0}},
    ),
    ChartDefinition(
        name="Max Ingestion Lag (s)",
        dataset_name="bronze_ingestion_lag",
        viz_type="big_number_total",
        metrics=("max_lag_seconds",),
        layout=(0, 6, 3, 3),
    ),
    ChartDefinition(
        name="Events by Topic",
        dataset_name="bronze_events_by_topic",
        viz_type="echarts_bar",
        metrics=("event_count",),
        dimensions=("topic",),
        layout=(0, 9, 3, 3),
    ),
    ChartDefinition(
        name="Partition Distribution",
        dataset_name="bronze_partition_distribution",
        viz_type="echarts_bar",
        metrics=("events",),
        dimensions=("partition",),
        layout=(3, 0, 6, 4),
    ),
    ChartDefinition(
        name="Ingestion Rate (Hourly)",
        dataset_name="bronze_ingestion_rate_hourly",
        viz_type="echarts_timeseries_line",
        metrics=("events",),
        time_column="hour",
        time_range="Last 24 hours",
        layout=(3, 6, 6, 4),
    ),
    ChartDefinition(
        name="DLQ Errors by Type",
        dataset_name="bronze_dlq_errors_by_type",
        viz_type="pie",
        metrics=("error_count",),
        dimensions=("error_type",),
        layout=(7, 0, 6, 4),
    ),
    ChartDefinition(
        name="Data Freshness",
        dataset_name="bronze_latest_ingestion",
        viz_type="table",
        metrics=(),
        dimensions=("topic", "latest_ingestion"),
        layout=(7, 6, 6, 4),
    ),
)

# =============================================================================
# Dashboard Definition
# =============================================================================

DATA_INGESTION_DASHBOARD = DashboardDefinition(
    title="Data Ingestion Monitoring",
    slug="bronze-pipeline",
    datasets=(
        TOTAL_EVENTS_24H,
        EVENTS_BY_TOPIC,
        INGESTION_RATE_HOURLY,
        DLQ_ERROR_COUNT,
        DLQ_ERRORS_BY_TYPE,
        PARTITION_DISTRIBUTION,
        LATEST_INGESTION,
        INGESTION_LAG,
    ),
    charts=CHARTS,
    required_tables=(
        "bronze.bronze_trips",
        "bronze.bronze_gps_pings",
        "bronze.bronze_dlq",
    ),
    refresh_interval=300,
    description="Monitor Bronze layer data ingestion from Kafka topics",
)
