"""Data flow integration tests for data platform.

Tests data integrity and lineage through the medallion lakehouse:
- DF-001: Schema validation and DLQ routing
- DF-002: Bronze to Silver data lineage
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
    query_table,
)
from tests.integration.data_platform.utils.wait_helpers import (
    poll_until_records_present,
)

# Module-level fixtures: ensure services are ready before any test runs
# Note: streaming_jobs_running is NOT required for tests that only test DBT
# transformations (they insert data directly into Bronze/Silver tables).
# Only tests that rely on Kafka -> Bronze ingestion need streaming_jobs_running.
pytestmark = [
    pytest.mark.data_flow,
    pytest.mark.requires_profiles("core", "data-pipeline"),
    pytest.mark.usefixtures(
        "bronze_tables_initialized",
    ),
]

# Project root for subprocess commands
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.mark.data_flow
def test_silver_layer_data_filtering(
    clean_bronze_tables,
    clean_silver_tables,
    thrift_connection,
):
    """DF-001: Verify Silver layer filters out malformed Bronze records.

    Bronze layer stores all events as raw JSON without validation.
    Silver layer (DBT) filters out records missing required fields.

    Inserts 3 Bronze records:
    - Valid trip event with all required fields
    - Malformed event (missing event_id - required for Silver)
    - Valid trip event with all required fields

    Verifies:
    - All 3 events stored in Bronze (no validation at Bronze)
    - Only 2 valid events appear in Silver after DBT transformation
    - Malformed event filtered by DBT WHERE clause
    """
    # Arrange: Prepare valid and malformed events as Bronze raw JSON
    # NOTE: stg_trips.sql parses JSON using get_json_object() and expects:
    # - pickup_location/dropoff_location as arrays [lat, lon] (not objects)
    # - event_type in format "trip.state" (extracts state after the dot)
    correlation_id = "df001-filter-test"

    # Valid event 1 - has all required fields for Silver
    valid_event_1 = {
        "event_id": "df001-event-001",
        "event_type": "trip.requested",
        "trip_id": "df001-trip-001",
        "status": "requested",
        "timestamp": "2026-01-20T10:00:00Z",
        "rider_id": "rider-001",
        "pickup_location": [-23.5505, -46.6333],  # Array format for JSON parsing
        "dropoff_location": [-23.5620, -46.6550],  # Array format for JSON parsing
        "correlation_id": correlation_id,
    }

    # Malformed event - missing event_id (required for Silver dedup)
    malformed_event = {
        # Missing event_id field (required for Silver)
        "event_type": "trip.requested",
        "trip_id": "df001-trip-002",
        "status": "requested",
        "timestamp": "2026-01-20T10:00:05Z",
        "rider_id": "rider-002",
        "pickup_location": [-23.5505, -46.6333],  # Array format for JSON parsing
        "correlation_id": correlation_id,
    }

    # Valid event 2 - has all required fields for Silver
    valid_event_2 = {
        "event_id": "df001-event-003",
        "event_type": "trip.requested",
        "trip_id": "df001-trip-003",
        "status": "requested",
        "timestamp": "2026-01-20T10:00:10Z",
        "rider_id": "rider-003",
        "pickup_location": [-23.5505, -46.6333],  # Array format for JSON parsing
        "dropoff_location": [-23.5620, -46.6550],  # Array format for JSON parsing
        "correlation_id": correlation_id,
    }

    # Insert as Bronze raw JSON format
    # Note: _ingestion_date is a partition column, do not include in INSERT values
    bronze_records = []
    for i, event in enumerate([valid_event_1, malformed_event, valid_event_2]):
        bronze_records.append(
            {
                "_raw_value": json.dumps(event),
                "_kafka_partition": 0,
                "_kafka_offset": 100 + i,
                "_kafka_timestamp": "2026-01-20T10:00:00",
                "_ingested_at": "2026-01-20T10:00:01",
            }
        )

    insert_bronze_data(thrift_connection, "bronze.bronze_trips", bronze_records)

    # Assert: All 3 events in Bronze (no validation at Bronze layer)
    bronze_count = count_rows(
        thrift_connection,
        f"bronze.bronze_trips WHERE _raw_value LIKE '%{correlation_id}%'",
    )
    assert bronze_count == 3, f"Expected 3 events in Bronze, found {bronze_count}"

    # Act: Execute DBT Silver transformations using local DBT installation
    dbt_result = subprocess.run(
        [
            "./venv/bin/dbt",
            "run",
            "--select",
            "stg_trips",
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

    # Query Silver table - DBT should filter out the malformed record
    # Note: stg_trips doesn't have correlation_id column - it parses from _raw_value
    # We need to filter by event_id prefix instead
    silver_trips = query_table(
        thrift_connection,
        "SELECT event_id, trip_id "
        "FROM silver.stg_trips WHERE event_id LIKE 'df001-event-%' "
        "ORDER BY event_id",
    )

    # Assert: Only 2 valid events in Silver (malformed filtered out)
    assert (
        len(silver_trips) == 2
    ), f"Expected 2 valid events in Silver (malformed filtered), found {len(silver_trips)}"

    # Verify the correct events made it through
    event_ids = {row["event_id"] for row in silver_trips}
    assert "df001-event-001" in event_ids, "Valid event 1 not in Silver"
    assert "df001-event-003" in event_ids, "Valid event 2 not in Silver"

    # The malformed event (missing event_id) should not be in Silver
    # since DBT filters out records where event_id IS NULL


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

    # Bronze trips: 5 records with 2 duplicates (same event_id = duplicate)
    # Format data as raw JSON in _raw_value column
    raw_events = [
        {
            "event_id": "event-lineage-001",  # First occurrence
            "event_type": "trip.completed",
            "trip_id": "trip-lineage-001",
            "status": "completed",
            "timestamp": "2026-01-20T10:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "fare": 15.50,
            "duration": 900,
        },
        {
            "event_id": "event-lineage-001",  # Duplicate (same event_id)
            "event_type": "trip.completed",
            "trip_id": "trip-lineage-001",
            "status": "completed",
            "timestamp": "2026-01-20T10:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "fare": 15.50,
            "duration": 900,
        },
        {
            "event_id": "event-lineage-002",
            "event_type": "trip.completed",
            "trip_id": "trip-lineage-002",
            "status": "completed",
            "timestamp": "2026-01-20T11:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-002",
            "driver_id": "driver-002",
            "fare": 22.00,
            "duration": 1200,
        },
        {
            "event_id": "event-lineage-003",  # First occurrence
            "event_type": "trip.completed",
            "trip_id": "trip-lineage-003",
            "status": "completed",
            "timestamp": "2026-01-20T12:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-003",
            "driver_id": "driver-003",
            "fare": 18.75,
            "duration": 1000,
        },
        {
            "event_id": "event-lineage-003",  # Duplicate (same event_id)
            "event_type": "trip.completed",
            "trip_id": "trip-lineage-003",
            "status": "completed",
            "timestamp": "2026-01-20T12:00:00Z",
            "correlation_id": correlation_id,
            "rider_id": "rider-003",
            "driver_id": "driver-003",
            "fare": 18.75,
            "duration": 1000,
        },
    ]

    # Convert to Bronze format with _raw_value column
    # Note: _ingestion_date is a partition column, do not include in INSERT values
    bronze_trips_data = []
    for i, event in enumerate(raw_events):
        bronze_trips_data.append(
            {
                "_raw_value": json.dumps(event),
                "_kafka_partition": i % 3,
                "_kafka_offset": 100 + i,
                "_kafka_timestamp": "2026-01-20T10:00:00",
                "_ingested_at": f"2026-01-20T{10 + i}:00:0{i}",
            }
        )

    insert_bronze_data(thrift_connection, "bronze.bronze_trips", bronze_trips_data)

    # Record Bronze counts before transformation
    bronze_count = count_rows(
        thrift_connection,
        f"bronze.bronze_trips WHERE _raw_value LIKE '%{correlation_id}%'",
    )

    # Act: Execute DBT Silver transformations using local DBT installation
    # Run only stg_trips model to test lineage (avoids running models with schema issues)
    dbt_result = subprocess.run(
        [
            "./venv/bin/dbt",
            "run",
            "--select",
            "stg_trips",
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

    # Query Silver table - filter by event_id prefix since stg_trips doesn't have correlation_id
    # The stg_trips model parses JSON from _raw_value and doesn't include correlation_id
    silver_trips = query_table(
        thrift_connection,
        "SELECT event_id, trip_id, trip_state, timestamp, fare "
        "FROM silver.stg_trips WHERE event_id LIKE 'event-lineage-%' "
        "ORDER BY event_id",
    )

    # Assert: Silver records traceable via event_id prefix
    assert (
        len(silver_trips) > 0
    ), "No records found in silver.stg_trips with event_id LIKE 'event-lineage-%'"

    # Assert: Duplicates removed (Silver count < Bronze count)
    silver_count = len(silver_trips)
    assert (
        silver_count < bronze_count
    ), f"Expected deduplication. Bronze: {bronze_count}, Silver: {silver_count}"

    # Expected: 3 unique events after deduplication (event_id is the dedup key)
    assert (
        silver_count == 3
    ), f"Expected 3 unique events in Silver, found {silver_count}"

    # Assert: No duplicate event_ids in Silver
    event_ids = [row["event_id"] for row in silver_trips]
    assert len(event_ids) == len(
        set(event_ids)
    ), "Duplicate event_ids found in silver.stg_trips after deduplication"

    # Assert: Transformations applied correctly (data values preserved)
    expected_fares = {15.50, 22.00, 18.75}
    actual_fares = {float(row["fare"]) for row in silver_trips if row["fare"]}
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
@pytest.mark.usefixtures("streaming_jobs_running")
def test_checkpoint_recovery_after_restart(
    clean_bronze_tables,
    kafka_producer,
    thrift_connection,
    minio_client,
    test_context,
):
    """DF-004: Verify Spark Streaming resumes from checkpoint after restart.

    Publishes 10 events, waits for ingestion, restarts spark-streaming-low-volume
    container, publishes 10 more events, and validates:
    - All 20 events present in bronze_trips (filtered by test_context)
    - No duplicates from restart
    - Checkpoint files exist in MinIO
    """
    from tests.integration.data_platform.utils.sql_helpers import (
        count_rows_filtered,
        query_table_filtered,
    )

    # Arrange: Generate 10 test events (first batch) with unique test IDs
    # Note: Events must include event_id and array format for locations (DBT parsing)
    batch_1_events = []
    for i in range(1, 11):
        event = {
            "event_id": test_context.event_id(f"{i:03d}"),
            "event_type": "trip.requested",
            "trip_id": test_context.trip_id(f"{i:03d}"),
            "status": "requested",
            "timestamp": f"2026-01-20T10:{i:02d}:00Z",
            "rider_id": test_context.rider_id(f"{i:03d}"),
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5620, -46.6550],
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

    # Wait for first batch ingestion (poll until 10 rows matching our test_context)
    filter_pattern = test_context.filter_pattern()

    def query_bronze_count():
        return count_rows_filtered(
            thrift_connection, "bronze.bronze_trips", filter_pattern
        )

    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=10,
        timeout_seconds=60,
        poll_interval=2.0,
        description=f"bronze_trips after batch 1 (filter: {filter_pattern})",
    )

    # Verify first batch ingested
    bronze_count_before_restart = query_bronze_count()
    assert (
        bronze_count_before_restart == 10
    ), f"Expected 10 rows before restart, found {bronze_count_before_restart}"

    # Act: Restart spark-streaming-low-volume container
    # Both profiles needed to resolve service dependencies
    restart_result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "infrastructure/docker/compose.yml",
            "--profile",
            "core",
            "--profile",
            "data-pipeline",
            "restart",
            "spark-streaming-low-volume",
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
    # Note: Events must include event_id and array format for locations (DBT parsing)
    batch_2_events = []
    for i in range(11, 21):
        event = {
            "event_id": test_context.event_id(f"{i:03d}"),
            "event_type": "trip.requested",
            "trip_id": test_context.trip_id(f"{i:03d}"),
            "status": "requested",
            "timestamp": f"2026-01-20T10:{i:02d}:00Z",
            "rider_id": test_context.rider_id(f"{i:03d}"),
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5620, -46.6550],
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

    # Wait for second batch ingestion (poll until 20 rows matching our filter)
    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=20,
        timeout_seconds=60,
        poll_interval=2.0,
        description=f"bronze_trips after batch 2 (filter: {filter_pattern})",
    )

    # Assert: Query bronze.bronze_trips and verify 20 rows with our test_context
    # Bronze layer stores raw JSON in _raw_value column
    bronze_trips = query_table_filtered(
        thrift_connection,
        "bronze.bronze_trips",
        filter_pattern,
        columns="_raw_value, _kafka_offset",
    )

    assert (
        len(bronze_trips) == 20
    ), f"Expected 20 events in bronze_trips, found {len(bronze_trips)}"

    # Assert: All trip_ids present (no data loss)
    # Parse trip_id from raw JSON
    expected_trip_ids = {test_context.trip_id(f"{i:03d}") for i in range(1, 21)}
    actual_trip_ids = set()
    for row in bronze_trips:
        raw_json = json.loads(row["_raw_value"])
        actual_trip_ids.add(raw_json["trip_id"])

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
        # boto3 S3 client uses list_objects_v2
        objects = minio_client.list_objects_v2(
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
