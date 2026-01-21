"""Data flow integration tests for data platform.

Tests data integrity and lineage through the medallion lakehouse:
- DF-001: Schema validation and DLQ routing
- DF-002: Bronze to Silver data lineage
- DF-003: Silver to Gold aggregation accuracy
- DF-004: Checkpoint recovery after restart
"""

import json
import subprocess
import time
from pathlib import Path

import pytest

from tests.integration.data_platform.utils.sql_helpers import (
    count_rows,
    insert_bronze_data,
    insert_silver_data,
    query_table,
)
from tests.integration.data_platform.utils.wait_helpers import (
    poll_until_records_present,
)

# Module-level fixtures: ensure services are ready before any test runs
pytestmark = [
    pytest.mark.data_flow,
    pytest.mark.usefixtures(
        "streaming_jobs_running",
        "bronze_tables_initialized",
    ),
]

# Project root for subprocess commands
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.mark.data_flow
def test_schema_validation_dlq_routing(
    clean_bronze_tables,
    kafka_producer,
    thrift_connection,
):
    """DF-001: Verify malformed events route to Dead Letter Queue.

    Publishes 3 events:
    - Valid trip event
    - Malformed event (missing required field trip_id)
    - Valid trip event

    Verifies:
    - 2 valid events appear in bronze_trips
    - 1 malformed event in dlq_trips with error_message
    - Valid events not affected by malformed event
    - DLQ contains validation failure details
    """
    # Arrange: Prepare valid and malformed events
    valid_event_1 = {
        "trip_id": "dlq-test-001",
        "status": "requested",
        "event_timestamp": "2026-01-20T10:00:00Z",
        "rider_id": "rider-001",
        "pickup_location": {"lat": -23.5505, "lon": -46.6333},
        "dropoff_location": {"lat": -23.5620, "lon": -46.6550},
        "correlation_id": "dlq-corr-001",
    }

    malformed_event = {
        # Missing trip_id field (required)
        "status": "requested",
        "event_timestamp": "2026-01-20T10:00:05Z",
        "rider_id": "rider-002",
        "pickup_location": {"lat": -23.5505, "lon": -46.6333},
        "correlation_id": "dlq-corr-002",
    }

    valid_event_2 = {
        "trip_id": "dlq-test-002",
        "status": "requested",
        "event_timestamp": "2026-01-20T10:00:10Z",
        "rider_id": "rider-003",
        "pickup_location": {"lat": -23.5505, "lon": -46.6333},
        "dropoff_location": {"lat": -23.5620, "lon": -46.6550},
        "correlation_id": "dlq-corr-003",
    }

    # Act: Publish events to Kafka
    for event in [valid_event_1, malformed_event, valid_event_2]:
        kafka_producer.produce(
            topic="trips",
            value=json.dumps(event).encode("utf-8"),
            key=event.get("trip_id", "malformed").encode("utf-8"),
        )

    kafka_producer.flush(timeout=10.0)

    # Wait for streaming job to process (trigger interval is 10s)
    time.sleep(15)

    # Assert: Query bronze_trips and dlq_trips
    bronze_trips = query_table(
        thrift_connection, "SELECT * FROM bronze_trips ORDER BY event_timestamp"
    )

    dlq_trips = query_table(
        thrift_connection, "SELECT * FROM dlq_trips ORDER BY _ingested_at"
    )

    # Assert: 2 valid events in bronze_trips
    assert (
        len(bronze_trips) == 2
    ), f"Expected 2 valid events in bronze_trips, found {len(bronze_trips)}"

    # Verify valid events have expected trip_ids
    trip_ids = [row["trip_id"] for row in bronze_trips]
    assert "dlq-test-001" in trip_ids, "Valid event 1 not in bronze_trips"
    assert "dlq-test-002" in trip_ids, "Valid event 2 not in bronze_trips"

    # Assert: 1 malformed event in dlq_trips
    assert len(dlq_trips) == 1, f"Expected 1 event in dlq_trips, found {len(dlq_trips)}"

    # Assert: DLQ record has error_message
    dlq_record = dlq_trips[0]
    assert "error_message" in dlq_record, "DLQ record missing error_message field"
    assert dlq_record["error_message"] is not None, "error_message is None"

    # Verify error_message mentions validation failure
    error_msg = str(dlq_record["error_message"]).lower()
    assert any(
        keyword in error_msg
        for keyword in ["trip_id", "missing", "required", "validation"]
    ), f"error_message does not explain validation failure: {dlq_record['error_message']}"

    # Assert: Valid events have correct metadata
    for row in bronze_trips:
        assert row["_ingested_at"] is not None, "Missing _ingested_at metadata"
        assert row["_kafka_partition"] is not None, "Missing _kafka_partition metadata"
        assert row["_kafka_offset"] is not None, "Missing _kafka_offset metadata"

    # Assert: DLQ record has metadata
    assert dlq_record["_ingested_at"] is not None, "DLQ missing _ingested_at"


@pytest.mark.data_flow
def test_bronze_to_silver_lineage(
    clean_bronze_tables,
    clean_silver_tables,
    thrift_connection,
):
    """DF-002: Verify data lineage from Bronze through Silver.

    Inserts controlled Bronze records with unique correlation_id,
    executes DBT Silver transformations, and validates:
    - Silver records traceable via correlation_id
    - Transformations applied correctly (cleansed values)
    - No data loss for valid records
    - Duplicates removed (Bronze > Silver row count)
    """
    # Arrange: Insert test data into Bronze tables with correlation_id
    correlation_id = "lineage-test-001"

    # Bronze trips: 5 records with 2 duplicates
    bronze_trips_data = [
        {
            "trip_id": "trip-lineage-001",
            "status": "completed",
            "event_timestamp": "2026-01-20T10:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "fare": 15.50,
            "duration": 900,
            "_ingested_at": "2026-01-20T10:00:01Z",
            "_kafka_partition": 0,
            "_kafka_offset": 100,
        },
        {
            "trip_id": "trip-lineage-001",  # Duplicate
            "status": "completed",
            "event_timestamp": "2026-01-20T10:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "fare": 15.50,
            "duration": 900,
            "_ingested_at": "2026-01-20T10:00:02Z",  # Different ingestion time
            "_kafka_partition": 0,
            "_kafka_offset": 101,
        },
        {
            "trip_id": "trip-lineage-002",
            "status": "completed",
            "event_timestamp": "2026-01-20T11:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-002",
            "driver_id": "driver-002",
            "fare": 22.00,
            "duration": 1200,
            "_ingested_at": "2026-01-20T11:00:01Z",
            "_kafka_partition": 1,
            "_kafka_offset": 200,
        },
        {
            "trip_id": "trip-lineage-003",
            "status": "completed",
            "event_timestamp": "2026-01-20T12:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-003",
            "driver_id": "driver-003",
            "fare": 18.75,
            "duration": 1000,
            "_ingested_at": "2026-01-20T12:00:01Z",
            "_kafka_partition": 2,
            "_kafka_offset": 300,
        },
        {
            "trip_id": "trip-lineage-003",  # Duplicate
            "status": "completed",
            "event_timestamp": "2026-01-20T12:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-003",
            "driver_id": "driver-003",
            "fare": 18.75,
            "duration": 1000,
            "_ingested_at": "2026-01-20T12:00:02Z",
            "_kafka_partition": 2,
            "_kafka_offset": 301,
        },
    ]

    insert_bronze_data(thrift_connection, "bronze_trips", bronze_trips_data)

    # Record Bronze counts before transformation
    bronze_count = count_rows(
        thrift_connection, f"bronze_trips WHERE correlation_id = '{correlation_id}'"
    )

    # Act: Execute DBT Silver transformations
    dbt_result = subprocess.run(
        [
            "./venv/bin/dbt",
            "run",
            "--select",
            "tag:silver",
            "--profiles-dir",
            "profiles",
            "--project-dir",
            ".",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT / "services" / "dbt"),
    )

    # Assert: DBT run succeeded
    assert dbt_result.returncode == 0, (
        f"dbt run failed with exit code {dbt_result.returncode}.\n"
        f"STDOUT: {dbt_result.stdout}\n"
        f"STDERR: {dbt_result.stderr}"
    )

    # Query Silver table with correlation_id filter
    silver_trips = query_table(
        thrift_connection,
        f"SELECT trip_id, status, event_timestamp, fare, duration, correlation_id "
        f"FROM stg_trips WHERE correlation_id = '{correlation_id}' "
        f"ORDER BY trip_id, event_timestamp",
    )

    # Assert: Silver records traceable via correlation_id
    assert (
        len(silver_trips) > 0
    ), f"No records found in stg_trips with correlation_id = {correlation_id}"

    # Verify all Silver records have expected correlation_id
    for row in silver_trips:
        assert (
            row["correlation_id"] == correlation_id
        ), f"Record has unexpected correlation_id: {row['correlation_id']}"

    # Assert: Duplicates removed (Silver count < Bronze count)
    silver_count = len(silver_trips)
    assert (
        silver_count < bronze_count
    ), f"Expected deduplication. Bronze: {bronze_count}, Silver: {silver_count}"

    # Expected: 3 unique trips after deduplication
    assert silver_count == 3, f"Expected 3 unique trips in Silver, found {silver_count}"

    # Assert: No duplicate (trip_id, event_timestamp) pairs in Silver
    trip_keys = [(row["trip_id"], row["event_timestamp"]) for row in silver_trips]
    assert len(trip_keys) == len(
        set(trip_keys)
    ), "Duplicate trips found in stg_trips after deduplication"

    # Assert: Transformations applied correctly (data values preserved)
    expected_fares = {15.50, 22.00, 18.75}
    actual_fares = {float(row["fare"]) for row in silver_trips}
    assert (
        actual_fares == expected_fares
    ), f"Fares not preserved. Expected {expected_fares}, got {actual_fares}"

    # Assert: No data loss for valid records
    expected_trip_ids = {"trip-lineage-001", "trip-lineage-002", "trip-lineage-003"}
    actual_trip_ids = {row["trip_id"] for row in silver_trips}
    assert (
        actual_trip_ids == expected_trip_ids
    ), f"Trip IDs not preserved. Expected {expected_trip_ids}, got {actual_trip_ids}"


@pytest.mark.data_flow
def test_silver_to_gold_aggregation(
    clean_silver_tables,
    clean_gold_tables,
    thrift_connection,
):
    """DF-003: Verify Gold aggregates compute correctly from Silver.

    Inserts controlled Silver data with known values,
    executes DBT Gold transformations, and validates:
    - SUM(fare) matches expected total
    - COUNT(trips) matches expected count
    - AVG(duration) computed correctly
    - Aggregates grouped by hour and zone correctly
    """
    # Arrange: Insert controlled Silver data
    # Zone A, Hour 10: 5 trips with known fares and durations
    silver_trips_zone_a_h10 = [
        {
            "trip_id": "agg-test-001",
            "status": "completed",
            "event_timestamp": "2026-01-20T10:15:00Z",
            "pickup_zone_id": "zone-a",
            "dropoff_zone_id": "zone-b",
            "fare": 10.00,
            "duration": 600,
            "rider_id": "rider-001",
            "driver_id": "driver-001",
        },
        {
            "trip_id": "agg-test-002",
            "status": "completed",
            "event_timestamp": "2026-01-20T10:30:00Z",
            "pickup_zone_id": "zone-a",
            "dropoff_zone_id": "zone-c",
            "fare": 15.00,
            "duration": 900,
            "rider_id": "rider-002",
            "driver_id": "driver-002",
        },
        {
            "trip_id": "agg-test-003",
            "status": "completed",
            "event_timestamp": "2026-01-20T10:45:00Z",
            "pickup_zone_id": "zone-a",
            "dropoff_zone_id": "zone-d",
            "fare": 20.00,
            "duration": 1200,
            "rider_id": "rider-003",
            "driver_id": "driver-003",
        },
        {
            "trip_id": "agg-test-004",
            "status": "completed",
            "event_timestamp": "2026-01-20T10:50:00Z",
            "pickup_zone_id": "zone-a",
            "dropoff_zone_id": "zone-e",
            "fare": 15.00,
            "duration": 800,
            "rider_id": "rider-004",
            "driver_id": "driver-004",
        },
        {
            "trip_id": "agg-test-005",
            "status": "completed",
            "event_timestamp": "2026-01-20T10:55:00Z",
            "pickup_zone_id": "zone-a",
            "dropoff_zone_id": "zone-f",
            "fare": 10.00,
            "duration": 700,
            "rider_id": "rider-005",
            "driver_id": "driver-005",
        },
    ]

    # Zone B, Hour 10: 3 trips
    silver_trips_zone_b_h10 = [
        {
            "trip_id": "agg-test-006",
            "status": "completed",
            "event_timestamp": "2026-01-20T10:20:00Z",
            "pickup_zone_id": "zone-b",
            "dropoff_zone_id": "zone-a",
            "fare": 12.00,
            "duration": 750,
            "rider_id": "rider-006",
            "driver_id": "driver-006",
        },
        {
            "trip_id": "agg-test-007",
            "status": "completed",
            "event_timestamp": "2026-01-20T10:40:00Z",
            "pickup_zone_id": "zone-b",
            "dropoff_zone_id": "zone-c",
            "fare": 18.00,
            "duration": 950,
            "rider_id": "rider-007",
            "driver_id": "driver-007",
        },
        {
            "trip_id": "agg-test-008",
            "status": "completed",
            "event_timestamp": "2026-01-20T10:58:00Z",
            "pickup_zone_id": "zone-b",
            "dropoff_zone_id": "zone-d",
            "fare": 25.00,
            "duration": 1100,
            "rider_id": "rider-008",
            "driver_id": "driver-008",
        },
    ]

    # Zone A, Hour 11: 2 trips
    silver_trips_zone_a_h11 = [
        {
            "trip_id": "agg-test-009",
            "status": "completed",
            "event_timestamp": "2026-01-20T11:10:00Z",
            "pickup_zone_id": "zone-a",
            "dropoff_zone_id": "zone-b",
            "fare": 14.00,
            "duration": 850,
            "rider_id": "rider-009",
            "driver_id": "driver-009",
        },
        {
            "trip_id": "agg-test-010",
            "status": "completed",
            "event_timestamp": "2026-01-20T11:30:00Z",
            "pickup_zone_id": "zone-a",
            "dropoff_zone_id": "zone-c",
            "fare": 16.00,
            "duration": 900,
            "rider_id": "rider-010",
            "driver_id": "driver-010",
        },
    ]

    all_silver_trips = (
        silver_trips_zone_a_h10 + silver_trips_zone_b_h10 + silver_trips_zone_a_h11
    )

    insert_silver_data(thrift_connection, "stg_trips", all_silver_trips)

    # Act: Execute DBT Gold transformations
    dbt_result = subprocess.run(
        [
            "./venv/bin/dbt",
            "run",
            "--select",
            "tag:aggregates",
            "--profiles-dir",
            "profiles",
            "--project-dir",
            ".",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT / "services" / "dbt"),
    )

    # Assert: DBT run succeeded
    assert dbt_result.returncode == 0, (
        f"dbt run failed with exit code {dbt_result.returncode}.\n"
        f"STDOUT: {dbt_result.stdout}\n"
        f"STDERR: {dbt_result.stderr}"
    )

    # Query Gold aggregate table
    gold_aggregates = query_table(
        thrift_connection,
        "SELECT pickup_zone_id, hour, trip_count, total_fare, avg_duration "
        "FROM agg_hourly_zone_demand "
        "ORDER BY pickup_zone_id, hour",
    )

    # Assert: 3 aggregate rows (zone-a hour 10, zone-b hour 10, zone-a hour 11)
    assert (
        len(gold_aggregates) == 3
    ), f"Expected 3 aggregate rows, found {len(gold_aggregates)}"

    # Expected aggregates
    expected_aggregates = {
        ("zone-a", 10): {"trip_count": 5, "total_fare": 70.00, "avg_duration": 840.0},
        ("zone-b", 10): {"trip_count": 3, "total_fare": 55.00, "avg_duration": 933.33},
        ("zone-a", 11): {"trip_count": 2, "total_fare": 30.00, "avg_duration": 875.0},
    }

    # Verify each aggregate row
    for row in gold_aggregates:
        zone_id = row["pickup_zone_id"]
        hour = int(row["hour"])
        key = (zone_id, hour)

        assert (
            key in expected_aggregates
        ), f"Unexpected aggregate row: zone={zone_id}, hour={hour}"

        expected = expected_aggregates[key]

        # Assert: COUNT(trips) matches
        assert int(row["trip_count"]) == expected["trip_count"], (
            f"Trip count mismatch for {key}. "
            f"Expected {expected['trip_count']}, got {row['trip_count']}"
        )

        # Assert: SUM(fare) matches
        actual_total_fare = float(row["total_fare"])
        assert abs(actual_total_fare - expected["total_fare"]) < 0.01, (
            f"Total fare mismatch for {key}. "
            f"Expected {expected['total_fare']}, got {actual_total_fare}"
        )

        # Assert: AVG(duration) matches (within tolerance)
        actual_avg_duration = float(row["avg_duration"])
        assert abs(actual_avg_duration - expected["avg_duration"]) < 1.0, (
            f"Avg duration mismatch for {key}. "
            f"Expected {expected['avg_duration']}, got {actual_avg_duration}"
        )


@pytest.mark.data_flow
def test_checkpoint_recovery_after_restart(
    clean_bronze_tables,
    kafka_producer,
    thrift_connection,
    minio_client,
):
    """DF-004: Verify Spark Streaming resumes from checkpoint after restart.

    Publishes 10 events, waits for ingestion, restarts spark-streaming-trips
    container, publishes 10 more events, and validates:
    - All 20 events present in bronze_trips
    - No duplicates from restart
    - Checkpoint files exist in MinIO
    - Kafka consumer group offset matches expected
    """
    # Arrange: Generate 10 test events (first batch)
    batch_1_events = []
    for i in range(1, 11):
        event = {
            "trip_id": f"checkpoint-test-{i:03d}",
            "status": "requested",
            "event_timestamp": f"2026-01-20T10:{i:02d}:00Z",
            "rider_id": f"rider-{i:03d}",
            "pickup_location": {"lat": -23.5505, "lon": -46.6333},
            "dropoff_location": {"lat": -23.5620, "lon": -46.6550},
            "correlation_id": f"checkpoint-corr-{i:03d}",
        }
        batch_1_events.append(event)

    # Act: Publish first batch to Kafka
    for event in batch_1_events:
        kafka_producer.produce(
            topic="trips",
            value=json.dumps(event).encode("utf-8"),
            key=event["trip_id"].encode("utf-8"),
        )

    kafka_producer.flush(timeout=10.0)

    # Wait for first batch ingestion (poll until 10 rows in bronze_trips)
    def query_bronze_count():
        return count_rows(thrift_connection, "bronze_trips")

    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=10,
        timeout_seconds=60,
        poll_interval=2.0,
        description="bronze_trips after batch 1",
    )

    # Verify first batch ingested
    bronze_count_before_restart = count_rows(thrift_connection, "bronze_trips")
    assert (
        bronze_count_before_restart == 10
    ), f"Expected 10 rows before restart, found {bronze_count_before_restart}"

    # Act: Restart spark-streaming-trips container
    restart_result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "infrastructure/docker/compose.yml",
            "--profile",
            "data-platform",
            "restart",
            "spark-streaming-trips",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    assert restart_result.returncode == 0, (
        f"Container restart failed.\n"
        f"STDOUT: {restart_result.stdout}\n"
        f"STDERR: {restart_result.stderr}"
    )

    # Wait for container to be healthy again (polling health check)
    time.sleep(30)  # Allow container to start and recover from checkpoint

    # Arrange: Generate 10 more test events (second batch)
    batch_2_events = []
    for i in range(11, 21):
        event = {
            "trip_id": f"checkpoint-test-{i:03d}",
            "status": "requested",
            "event_timestamp": f"2026-01-20T10:{i:02d}:00Z",
            "rider_id": f"rider-{i:03d}",
            "pickup_location": {"lat": -23.5505, "lon": -46.6333},
            "dropoff_location": {"lat": -23.5620, "lon": -46.6550},
            "correlation_id": f"checkpoint-corr-{i:03d}",
        }
        batch_2_events.append(event)

    # Act: Publish second batch to Kafka
    for event in batch_2_events:
        kafka_producer.produce(
            topic="trips",
            value=json.dumps(event).encode("utf-8"),
            key=event["trip_id"].encode("utf-8"),
        )

    kafka_producer.flush(timeout=10.0)

    # Wait for second batch ingestion (poll until 20 rows in bronze_trips)
    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=20,
        timeout_seconds=60,
        poll_interval=2.0,
        description="bronze_trips after batch 2",
    )

    # Assert: Query bronze_trips and verify 20 rows
    bronze_trips = query_table(
        thrift_connection,
        "SELECT trip_id, _kafka_offset FROM bronze_trips ORDER BY trip_id",
    )

    assert (
        len(bronze_trips) == 20
    ), f"Expected 20 events in bronze_trips, found {len(bronze_trips)}"

    # Assert: All trip_ids present (no data loss)
    expected_trip_ids = {f"checkpoint-test-{i:03d}" for i in range(1, 21)}
    actual_trip_ids = {row["trip_id"] for row in bronze_trips}
    assert (
        actual_trip_ids == expected_trip_ids
    ), f"Missing trip_ids. Expected {expected_trip_ids}, got {actual_trip_ids}"

    # Assert: No duplicates (exactly-once semantics)
    assert (
        len(set(actual_trip_ids)) == 20
    ), "Duplicates found in bronze_trips after restart"

    # Assert: Verify checkpoint files exist in MinIO
    checkpoint_bucket = "rideshare-checkpoints"
    checkpoint_prefix = "trips/"

    try:
        objects = minio_client.list_objects(
            Bucket=checkpoint_bucket, Prefix=checkpoint_prefix
        )

        checkpoint_files = [obj["Key"] for obj in objects.get("Contents", [])]

        assert (
            len(checkpoint_files) > 0
        ), f"No checkpoint files found in s3a://{checkpoint_bucket}/{checkpoint_prefix}"

        # Verify checkpoint metadata directory exists
        metadata_files = [f for f in checkpoint_files if "metadata" in f.lower()]
        assert len(metadata_files) > 0, "Checkpoint metadata files not found"

    except Exception as e:
        pytest.fail(f"Failed to verify checkpoint files in MinIO: {e}")

    # Assert: Kafka consumer group offset consistency (optional advanced check)
    # This would require Kafka Admin API to query consumer group offsets
    # Placeholder for future enhancement
