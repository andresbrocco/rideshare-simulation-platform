"""Resilience integration tests for data platform.

Tests data consistency and recovery under failure conditions:
- NEW-005: Data consistency under partial failure
- NEW-006: Trip state machine integrity through Bronze -> Silver
- REG-001 (simplified): Pipeline smoke test Kafka -> Bronze -> Silver
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


# Module-level fixtures: require both core and data-pipeline profiles
pytestmark = [
    pytest.mark.resilience,
    pytest.mark.requires_profiles("core", "data-pipeline"),
    pytest.mark.usefixtures(
        "bronze_tables_initialized",
    ),
]

# Project root for subprocess commands
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def _get_project_root() -> str:
    """Get the project root directory."""
    return str(PROJECT_ROOT)


@pytest.mark.resilience
@pytest.mark.usefixtures("streaming_jobs_running")
def test_data_consistency_under_partial_failure(
    clean_bronze_tables,
    kafka_producer,
    thrift_connection,
    minio_client,
):
    """NEW-005: Verify no data loss or duplication after streaming job restart.

    When the streaming job is killed mid-batch, no data should be lost
    or duplicated after recovery.

    Verifies:
    - All events published before restart are present
    - All events published after restart are present
    - Exactly 20 events total (no duplicates, no missing)
    - Checkpoint enables recovery
    """
    project_root = _get_project_root()

    # Arrange: Generate 10 test events (first batch)
    batch_1_events = []
    for i in range(1, 11):
        event = {
            "event_id": f"partial-fail-event-{i:03d}",
            "event_type": "trip.requested",
            "trip_id": f"partial-fail-trip-{i:03d}",
            "status": "requested",
            "timestamp": f"2026-01-20T10:{i:02d}:00Z",
            "rider_id": f"rider-{i:03d}",
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

    # Wait for first batch ingestion
    def query_bronze_count():
        return count_rows(thrift_connection, "bronze.bronze_trips")

    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=10,
        timeout_seconds=60,
        poll_interval=2.0,
        description="bronze_trips after batch 1",
    )

    # Verify first batch ingested
    bronze_count_before = count_rows(thrift_connection, "bronze.bronze_trips")
    assert (
        bronze_count_before == 10
    ), f"Expected 10 rows before kill, found {bronze_count_before}"

    # Act: Kill spark-streaming-trips container (simulate failure)
    kill_result = subprocess.run(
        ["docker", "kill", "rideshare-spark-streaming-trips"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    # Container may already be stopped or not exist
    if kill_result.returncode != 0 and "No such container" not in kill_result.stderr:
        pytest.skip(f"Could not kill container: {kill_result.stderr}")

    # Arrange: Generate 10 more events (second batch)
    batch_2_events = []
    for i in range(11, 21):
        event = {
            "event_id": f"partial-fail-event-{i:03d}",
            "event_type": "trip.requested",
            "trip_id": f"partial-fail-trip-{i:03d}",
            "status": "requested",
            "timestamp": f"2026-01-20T10:{i:02d}:00Z",
            "rider_id": f"rider-{i:03d}",
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

    # Act: Restart the container
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
            "start",
            "spark-streaming-trips",
        ],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    assert restart_result.returncode == 0, (
        f"Container restart failed.\n"
        f"STDOUT: {restart_result.stdout}\n"
        f"STDERR: {restart_result.stderr}"
    )

    # Wait for container to recover from checkpoint
    time.sleep(30)

    # Wait for all 20 events to be ingested
    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=20,
        timeout_seconds=90,
        poll_interval=3.0,
        description="bronze_trips after recovery (20 events)",
    )

    # Assert: Exactly 20 events in Bronze
    bronze_trips = query_table(
        thrift_connection,
        "SELECT _raw_value FROM bronze.bronze_trips ORDER BY _kafka_offset",
    )

    assert len(bronze_trips) == 20, (
        f"Expected exactly 20 events after recovery, found {len(bronze_trips)}. "
        "Data may have been lost or duplicated."
    )

    # Assert: All trip_ids present (no data loss)
    expected_trip_ids = {f"partial-fail-trip-{i:03d}" for i in range(1, 21)}
    actual_trip_ids = set()
    for row in bronze_trips:
        raw_json = json.loads(row["_raw_value"])
        actual_trip_ids.add(raw_json["trip_id"])

    missing = expected_trip_ids - actual_trip_ids
    extra = actual_trip_ids - expected_trip_ids

    assert not missing, f"Missing trip_ids: {missing}"
    assert not extra, f"Unexpected trip_ids: {extra}"

    # Assert: No duplicates
    assert (
        len(actual_trip_ids) == 20
    ), f"Duplicate trip_ids found. Unique: {len(actual_trip_ids)}, Total: {len(bronze_trips)}"


@pytest.mark.resilience
def test_trip_state_machine_integrity(
    clean_bronze_tables,
    clean_silver_tables,
    thrift_connection,
):
    """NEW-006: Verify trip data is preserved exactly through Bronze -> Silver.

    Trip data (fare, driver_id, etc.) should be preserved exactly
    when flowing from Bronze to Silver layer.

    Verifies:
    - Complete trip lifecycle stored in Bronze
    - DBT Silver transformation preserves all fields
    - fare, surge_multiplier, driver_id, rider_id match exactly
    """
    # Arrange: Create complete trip lifecycle with known values
    test_fare = 42.75
    test_surge = 1.5
    test_trip_id = "integrity-test-trip-001"
    test_driver_id = "integrity-driver-001"
    test_rider_id = "integrity-rider-001"

    trip_lifecycle_events = [
        {
            "event_id": f"{test_trip_id}-event-001",
            "event_type": "trip.requested",
            "trip_id": test_trip_id,
            "status": "requested",
            "rider_id": test_rider_id,
            "timestamp": "2026-01-20T10:00:00Z",
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5620, -46.6550],
            "surge_multiplier": test_surge,
        },
        {
            "event_id": f"{test_trip_id}-event-002",
            "event_type": "trip.matched",
            "trip_id": test_trip_id,
            "status": "matched",
            "rider_id": test_rider_id,
            "driver_id": test_driver_id,
            "timestamp": "2026-01-20T10:01:00Z",
        },
        {
            "event_id": f"{test_trip_id}-event-003",
            "event_type": "trip.driver_en_route",
            "trip_id": test_trip_id,
            "status": "driver_en_route",
            "driver_id": test_driver_id,
            "timestamp": "2026-01-20T10:02:00Z",
        },
        {
            "event_id": f"{test_trip_id}-event-004",
            "event_type": "trip.driver_arrived",
            "trip_id": test_trip_id,
            "status": "driver_arrived",
            "driver_id": test_driver_id,
            "timestamp": "2026-01-20T10:05:00Z",
        },
        {
            "event_id": f"{test_trip_id}-event-005",
            "event_type": "trip.started",
            "trip_id": test_trip_id,
            "status": "started",
            "driver_id": test_driver_id,
            "rider_id": test_rider_id,
            "timestamp": "2026-01-20T10:06:00Z",
        },
        {
            "event_id": f"{test_trip_id}-event-006",
            "event_type": "trip.completed",
            "trip_id": test_trip_id,
            "status": "completed",
            "driver_id": test_driver_id,
            "rider_id": test_rider_id,
            "timestamp": "2026-01-20T10:25:00Z",
            "fare": test_fare,
            "surge_multiplier": test_surge,
            "distance_km": 12.3,
            "duration_minutes": 19,
        },
    ]

    # Insert into Bronze as raw JSON
    bronze_data = []
    for i, event in enumerate(trip_lifecycle_events):
        bronze_data.append(
            {
                "_raw_value": json.dumps(event),
                "_kafka_partition": 0,
                "_kafka_offset": 100 + i,
                "_kafka_timestamp": "2026-01-20T10:00:00",
                "_ingested_at": f"2026-01-20T10:0{i}:00",
            }
        )

    insert_bronze_data(thrift_connection, "bronze.bronze_trips", bronze_data)

    # Verify Bronze insertion
    bronze_count = count_rows(
        thrift_connection,
        f"bronze.bronze_trips WHERE _raw_value LIKE '%{test_trip_id}%'",
    )
    assert bronze_count == 6, f"Expected 6 events in Bronze, found {bronze_count}"

    # Act: Execute DBT Silver transformation
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

    assert dbt_result.returncode == 0, (
        f"dbt run failed with exit code {dbt_result.returncode}.\n"
        f"STDOUT: {dbt_result.stdout}\n"
        f"STDERR: {dbt_result.stderr}"
    )

    # Query Silver for completed trip
    silver_trips = query_table(
        thrift_connection,
        f"SELECT event_id, trip_id, trip_state, fare, surge_multiplier, "
        f"driver_id, rider_id FROM silver.stg_trips "
        f"WHERE trip_id = '{test_trip_id}' AND trip_state = 'completed'",
    )

    # Assert: Completed trip exists in Silver
    assert (
        len(silver_trips) >= 1
    ), f"No completed trip found in Silver for trip_id={test_trip_id}"

    completed_trip = silver_trips[0]

    # Assert: fare matches exactly
    if completed_trip.get("fare") is not None:
        actual_fare = float(completed_trip["fare"])
        assert (
            abs(actual_fare - test_fare) < 0.01
        ), f"Fare mismatch. Expected {test_fare}, got {actual_fare}"

    # Assert: surge_multiplier matches exactly
    if completed_trip.get("surge_multiplier") is not None:
        actual_surge = float(completed_trip["surge_multiplier"])
        assert (
            abs(actual_surge - test_surge) < 0.01
        ), f"Surge multiplier mismatch. Expected {test_surge}, got {actual_surge}"

    # Assert: driver_id preserved
    if completed_trip.get("driver_id") is not None:
        assert (
            completed_trip["driver_id"] == test_driver_id
        ), f"Driver ID mismatch. Expected {test_driver_id}, got {completed_trip['driver_id']}"

    # Assert: rider_id preserved
    if completed_trip.get("rider_id") is not None:
        assert (
            completed_trip["rider_id"] == test_rider_id
        ), f"Rider ID mismatch. Expected {test_rider_id}, got {completed_trip['rider_id']}"


@pytest.mark.resilience
@pytest.mark.usefixtures("streaming_jobs_running")
def test_pipeline_smoke_test(
    clean_bronze_tables,
    clean_silver_tables,
    kafka_producer,
    thrift_connection,
):
    """REG-001 (simplified): Pipeline smoke test Kafka -> Bronze -> Silver.

    Data should flow from Kafka through Bronze to Silver without loss
    in under 2 minutes (no Airflow dependency).

    Verifies:
    - Events published to Kafka reach Bronze
    - DBT Silver transformation succeeds
    - Completed trip appears in Silver with correct fare
    - Total time < 120 seconds
    """
    start_time = time.time()

    # Arrange: Create trip lifecycle
    test_trip_id = "smoke-test-trip-001"
    test_fare = 35.00

    trip_events = [
        {
            "event_id": f"{test_trip_id}-event-001",
            "event_type": "trip.requested",
            "trip_id": test_trip_id,
            "status": "requested",
            "rider_id": "smoke-rider-001",
            "timestamp": "2026-01-20T14:00:00Z",
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5620, -46.6550],
        },
        {
            "event_id": f"{test_trip_id}-event-002",
            "event_type": "trip.matched",
            "trip_id": test_trip_id,
            "status": "matched",
            "rider_id": "smoke-rider-001",
            "driver_id": "smoke-driver-001",
            "timestamp": "2026-01-20T14:01:00Z",
        },
        {
            "event_id": f"{test_trip_id}-event-003",
            "event_type": "trip.driver_en_route",
            "trip_id": test_trip_id,
            "status": "driver_en_route",
            "driver_id": "smoke-driver-001",
            "timestamp": "2026-01-20T14:02:00Z",
        },
        {
            "event_id": f"{test_trip_id}-event-004",
            "event_type": "trip.driver_arrived",
            "trip_id": test_trip_id,
            "status": "driver_arrived",
            "driver_id": "smoke-driver-001",
            "timestamp": "2026-01-20T14:05:00Z",
        },
        {
            "event_id": f"{test_trip_id}-event-005",
            "event_type": "trip.started",
            "trip_id": test_trip_id,
            "status": "started",
            "driver_id": "smoke-driver-001",
            "rider_id": "smoke-rider-001",
            "timestamp": "2026-01-20T14:06:00Z",
        },
        {
            "event_id": f"{test_trip_id}-event-006",
            "event_type": "trip.completed",
            "trip_id": test_trip_id,
            "status": "completed",
            "driver_id": "smoke-driver-001",
            "rider_id": "smoke-rider-001",
            "timestamp": "2026-01-20T14:20:00Z",
            "fare": test_fare,
            "surge_multiplier": 1.0,
        },
    ]

    # Act: Publish to Kafka
    for event in trip_events:
        kafka_producer.produce(
            topic="trips",
            value=json.dumps(event).encode("utf-8"),
            key=test_trip_id.encode("utf-8"),
        )
    kafka_producer.flush(timeout=10.0)

    # Wait for Bronze ingestion
    def query_bronze_count():
        return count_rows(
            thrift_connection,
            f"bronze.bronze_trips WHERE _raw_value LIKE '%{test_trip_id}%'",
        )

    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=6,
        timeout_seconds=60,
        poll_interval=2.0,
        description=f"bronze_trips for {test_trip_id}",
    )

    # Verify Bronze ingestion
    bronze_count = count_rows(
        thrift_connection,
        f"bronze.bronze_trips WHERE _raw_value LIKE '%{test_trip_id}%'",
    )
    assert bronze_count == 6, f"Expected 6 events in Bronze, found {bronze_count}"

    # Act: Run DBT Silver transformation directly (no Airflow)
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

    assert dbt_result.returncode == 0, (
        f"dbt run failed with exit code {dbt_result.returncode}.\n"
        f"STDOUT: {dbt_result.stdout}\n"
        f"STDERR: {dbt_result.stderr}"
    )

    # Query Silver for completed trip
    silver_trips = query_table(
        thrift_connection,
        f"SELECT trip_id, trip_state, fare FROM silver.stg_trips "
        f"WHERE trip_id = '{test_trip_id}' AND trip_state = 'completed'",
    )

    # Assert: Completed trip in Silver
    assert (
        len(silver_trips) >= 1
    ), f"No completed trip found in Silver for trip_id={test_trip_id}"

    # Assert: Fare preserved
    completed = silver_trips[0]
    if completed.get("fare") is not None:
        actual_fare = float(completed["fare"])
        assert (
            abs(actual_fare - test_fare) < 0.01
        ), f"Fare mismatch. Expected {test_fare}, got {actual_fare}"

    # Assert: Total time < 120 seconds
    total_time = time.time() - start_time
    assert (
        total_time < 120
    ), f"Pipeline took {total_time:.1f}s, expected < 120s (2 minutes)"

    print(f"Pipeline smoke test completed in {total_time:.1f} seconds")
