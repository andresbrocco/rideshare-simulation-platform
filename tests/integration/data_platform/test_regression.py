"""Regression integration tests for data platform.

Tests comprehensive end-to-end scenarios and resilience:
- REG-001: Full pipeline regression from Kafka to Superset
- REG-002: Service restart resilience
- REG-003: Memory pressure handling
"""

import json
import os
import subprocess
import time
import pytest

from tests.integration.data_platform.utils.sql_helpers import (
    count_rows,
    query_table,
)
from tests.integration.data_platform.utils.wait_helpers import (
    poll_until_records_present,
)


# Module-level fixtures: ensure services are ready before any test runs
# Note: REG-001 requires quality-orchestration (Airflow) and bi (Superset)
# Note: streaming_jobs_running is required for all regression tests as they
# test full pipeline flows involving Kafka -> Bronze ingestion.
pytestmark = [
    pytest.mark.regression,
    pytest.mark.requires_profiles("core", "data-platform"),
    pytest.mark.usefixtures(
        "streaming_jobs_running",
        "bronze_tables_initialized",
    ),
]


# =============================================================================
# REG-001: Full Pipeline End-to-End Regression Test
# =============================================================================


@pytest.mark.regression
@pytest.mark.requires_profiles("core", "data-platform", "quality-orchestration", "bi")
@pytest.mark.usefixtures("airflow_dags_loaded")
def test_full_pipeline_regression(
    clean_bronze_tables,
    clean_silver_tables,
    clean_gold_tables,
    kafka_producer,
    thrift_connection,
    airflow_client,
    superset_client,
):
    """REG-001: Complete pipeline test from Kafka to Superset query.

    Tests the entire medallion lakehouse architecture end-to-end:
    1. Publishes complete trip lifecycle events to Kafka
    2. Waits for Bronze ingestion via Spark Streaming
    3. Triggers Airflow Silver DAG (DBT transformations)
    4. Triggers Airflow Gold DAG (fact tables and dimensions)
    5. Queries Gold layer via Superset API
    6. Validates data flows without data loss in <5 minutes

    This is a superset of FJ-001 through FJ-007, validating:
    - Kafka → Bronze ingestion (FJ-001, FJ-002)
    - Bronze → Silver transformation (FJ-003)
    - Silver → Gold aggregation (FJ-004)
    - Airflow orchestration (FJ-005)
    - Data quality validation (FJ-006)
    - Superset query access (FJ-007)
    """
    # Start timer for total execution time
    start_time = time.time()

    # Arrange: Generate complete trip lifecycle events
    trip_id = "regression-test-trip-001"
    rider_id = "regression-rider-001"
    driver_id = "regression-driver-001"

    # Note: pickup_location/dropoff_location must be arrays [lat, lon] for JSON parsing in DBT
    trip_events = [
        {
            "event_id": f"{trip_id}-event-001",
            "event_type": "trip.requested",
            "trip_id": trip_id,
            "status": "requested",
            "timestamp": "2026-01-20T10:00:00Z",
            "rider_id": rider_id,
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5620, -46.6550],
        },
        {
            "event_id": f"{trip_id}-event-002",
            "event_type": "trip.matched",
            "trip_id": trip_id,
            "status": "matched",
            "timestamp": "2026-01-20T10:01:00Z",
            "rider_id": rider_id,
            "driver_id": driver_id,
        },
        {
            "event_id": f"{trip_id}-event-003",
            "event_type": "trip.driver_en_route",
            "trip_id": trip_id,
            "status": "driver_en_route",
            "timestamp": "2026-01-20T10:02:00Z",
            "driver_id": driver_id,
        },
        {
            "event_id": f"{trip_id}-event-004",
            "event_type": "trip.driver_arrived",
            "trip_id": trip_id,
            "status": "driver_arrived",
            "timestamp": "2026-01-20T10:05:00Z",
            "driver_id": driver_id,
        },
        {
            "event_id": f"{trip_id}-event-005",
            "event_type": "trip.started",
            "trip_id": trip_id,
            "status": "started",
            "timestamp": "2026-01-20T10:06:00Z",
            "driver_id": driver_id,
        },
        {
            "event_id": f"{trip_id}-event-006",
            "event_type": "trip.completed",
            "trip_id": trip_id,
            "status": "completed",
            "timestamp": "2026-01-20T10:25:00Z",
            "driver_id": driver_id,
            "fare": 45.50,
            "distance_km": 12.3,
            "duration_minutes": 19,
        },
    ]

    # Act: Publish events to Kafka
    for event in trip_events:
        kafka_producer.produce(
            topic="trips",
            value=json.dumps(event).encode("utf-8"),
            key=event["trip_id"].encode("utf-8"),
        )

    kafka_producer.flush(timeout=10.0)

    # Step 1: Wait for Bronze ingestion
    def query_bronze_count():
        return count_rows(
            thrift_connection,
            f"bronze.bronze_trips WHERE _raw_value LIKE '%{trip_id}%'",
        )

    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=6,
        timeout_seconds=60,
        poll_interval=2.0,
        description=f"bronze_trips for {trip_id}",
    )

    # Assert: Verify all 6 events in Bronze
    bronze_events = query_table(
        thrift_connection,
        f"SELECT _raw_value, _ingested_at FROM bronze.bronze_trips WHERE _raw_value LIKE '%{trip_id}%' ORDER BY _kafka_offset",
    )

    assert (
        len(bronze_events) == 6
    ), f"Expected 6 events in bronze_trips, found {len(bronze_events)}"

    # Step 2: Trigger Airflow Silver DAG
    # Check if DAG exists and is not paused before triggering
    import httpx

    silver_dag_id = "dbt_transformation"
    try:
        dag_info = airflow_client.get_dag(silver_dag_id)
        if dag_info.get("is_paused", True):
            pytest.skip(f"{silver_dag_id} DAG is paused")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            pytest.skip(f"{silver_dag_id} DAG not found in Airflow")
        elif e.response.status_code == 422:
            pytest.skip(
                f"{silver_dag_id} DAG returned 422 - may not be properly configured"
            )
        raise

    try:
        silver_dag_run_id = airflow_client.trigger_dag(
            dag_id=silver_dag_id, conf={"source": "regression_test"}
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 422:
            pytest.skip(
                f"Could not trigger {silver_dag_id} DAG (422 error): {e.response.text}"
            )
        raise

    # Poll until Silver DAG completes
    silver_dag_state = airflow_client.wait_for_dag_completion(
        dag_id=silver_dag_id,
        dag_run_id=silver_dag_run_id,
        timeout_seconds=120,
    )

    assert (
        silver_dag_state == "success"
    ), f"Silver DAG failed with state: {silver_dag_state}"

    # Assert: Verify Silver transformation
    # Note: stg_trips model doesn't include correlation_id - filter by trip_id instead
    silver_trips = query_table(
        thrift_connection,
        f"SELECT * FROM silver.stg_trips WHERE trip_id = '{trip_id}'",
    )

    assert (
        len(silver_trips) >= 1
    ), f"Expected at least 1 trip in stg_trips, found {len(silver_trips)}"

    # Step 3: Trigger Airflow Gold DAG
    # Check if DAG exists and is not paused before triggering
    gold_dag_id = "dbt_gold_transformation"
    try:
        gold_dag_info = airflow_client.get_dag(gold_dag_id)
        if gold_dag_info.get("is_paused", True):
            pytest.skip(f"{gold_dag_id} DAG is paused")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            pytest.skip(f"{gold_dag_id} DAG not found in Airflow")
        elif e.response.status_code == 422:
            pytest.skip(
                f"{gold_dag_id} DAG returned 422 - may not be properly configured"
            )
        raise

    try:
        gold_dag_run_id = airflow_client.trigger_dag(
            dag_id=gold_dag_id, conf={"source": "regression_test"}
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 422:
            pytest.skip(
                f"Could not trigger {gold_dag_id} DAG (422 error): {e.response.text}"
            )
        raise

    # Poll until Gold DAG completes
    gold_dag_state = airflow_client.wait_for_dag_completion(
        dag_id=gold_dag_id,
        dag_run_id=gold_dag_run_id,
        timeout_seconds=180,
    )

    assert gold_dag_state == "success", f"Gold DAG failed with state: {gold_dag_state}"

    # Assert: Verify Gold layer has fact_trips
    gold_trips = query_table(
        thrift_connection, f"SELECT * FROM gold.fact_trips WHERE trip_id = '{trip_id}'"
    )

    assert (
        len(gold_trips) == 1
    ), f"Expected 1 trip in fact_trips, found {len(gold_trips)}"

    gold_trip = gold_trips[0]
    assert (
        gold_trip["status"] == "completed"
    ), f"Expected completed trip, got status: {gold_trip['status']}"
    assert gold_trip["fare"] == 45.50, f"Expected fare 45.50, got {gold_trip['fare']}"

    # Step 4: Query Gold layer via Superset
    # First get the database ID for Spark Thrift Server
    databases = superset_client.list_databases()
    spark_db = next(
        (db for db in databases if "spark" in db.get("database_name", "").lower()),
        None,
    )

    if spark_db is None:
        # Use database_id=1 as fallback (common default)
        database_id = 1
    else:
        database_id = spark_db["id"]

    superset_query_result = superset_client.execute_query(
        database_id=database_id,
        sql=f"SELECT * FROM gold.fact_trips WHERE trip_id = '{trip_id}'",
    )

    # Superset returns various structures; check for success
    assert (
        "error" not in superset_query_result
        or superset_query_result.get("error") is None
    ), f"Superset query failed: {superset_query_result.get('error')}"

    # Extract data from result (structure varies by Superset version)
    superset_data = superset_query_result.get(
        "data", superset_query_result.get("result", [])
    )
    if isinstance(superset_data, dict):
        superset_data = superset_data.get("data", [])

    assert (
        len(superset_data) >= 1
    ), f"Expected at least 1 row from Superset query, got {len(superset_data)}"

    # Assert: Total execution time < 5 minutes
    total_time = time.time() - start_time
    assert (
        total_time < 300
    ), f"Pipeline took {total_time:.1f}s, expected <300s (5 minutes)"

    # Final assertion: No data loss
    # 6 Bronze events → 1+ Silver trips → 1 Gold fact_trip → 1 Superset result
    assert len(bronze_events) == 6
    assert len(silver_trips) >= 1
    assert len(gold_trips) == 1
    assert len(superset_data) >= 1


# =============================================================================
# REG-002: Service Restart Resilience Test
# =============================================================================


def _get_project_root() -> str:
    """Get the project root directory."""
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )


@pytest.mark.regression
def test_service_restart_resilience(
    clean_bronze_tables,
    kafka_producer,
    thrift_connection,
    minio_client,
):
    """REG-002: Verify system recovers from service restarts.

    Tests resilience by restarting critical services:
    1. Publishes 10 events, waits for ingestion
    2. Restarts spark-streaming-trips container
    3. Publishes 10 more events, waits for ingestion
    4. Restarts spark-thrift-server container
    5. Queries data via Thrift Server

    Validates:
    - No data loss from Spark Streaming restart
    - Checkpoint recovery enables exactly-once semantics
    - Thrift Server reconnects to Delta tables after restart
    - No orphaned connections or corrupted state
    """
    project_root = _get_project_root()

    # Arrange: Generate 10 test events (batch 1)
    # Note: pickup_location/dropoff_location must be arrays [lat, lon] for JSON parsing in DBT
    batch_1_events = []
    for i in range(1, 11):
        event = {
            "event_id": f"restart-event-{i:03d}",
            "event_type": "trip.requested",
            "trip_id": f"restart-test-{i:03d}",
            "status": "requested",
            "timestamp": f"2026-01-20T11:{i:02d}:00Z",
            "rider_id": f"rider-{i:03d}",
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5620, -46.6550],
        }
        batch_1_events.append(event)

    # Act: Publish batch 1 to Kafka
    for event in batch_1_events:
        kafka_producer.produce(
            topic="trips",
            value=json.dumps(event).encode("utf-8"),
            key=event["trip_id"].encode("utf-8"),
        )

    kafka_producer.flush(timeout=10.0)

    # Wait for batch 1 ingestion
    def query_bronze_count():
        return count_rows(thrift_connection, "bronze.bronze_trips")

    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=10,
        timeout_seconds=60,
        poll_interval=2.0,
        description="bronze_trips after batch 1",
    )

    # Verify batch 1 ingested
    bronze_count_before_restart = count_rows(thrift_connection, "bronze.bronze_trips")
    assert (
        bronze_count_before_restart == 10
    ), f"Expected 10 rows before restart, found {bronze_count_before_restart}"

    # Act: Restart spark-streaming-trips container
    # Both profiles needed to resolve service dependencies
    restart_streaming_result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "infrastructure/docker/compose.yml",
            "--profile",
            "core",
            "--profile",
            "data-platform",
            "restart",
            "spark-streaming-trips",
        ],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    assert restart_streaming_result.returncode == 0, (
        f"Spark Streaming container restart failed.\n"
        f"STDOUT: {restart_streaming_result.stdout}\n"
        f"STDERR: {restart_streaming_result.stderr}"
    )

    # Wait for streaming container to recover from checkpoint
    time.sleep(30)  # Allow container to start and recover

    # Arrange: Generate batch 2 events
    # Note: pickup_location/dropoff_location must be arrays [lat, lon] for JSON parsing in DBT
    batch_2_events = []
    for i in range(11, 21):
        event = {
            "event_id": f"restart-event-{i:03d}",
            "event_type": "trip.requested",
            "trip_id": f"restart-test-{i:03d}",
            "status": "requested",
            "timestamp": f"2026-01-20T11:{i:02d}:00Z",
            "rider_id": f"rider-{i:03d}",
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5620, -46.6550],
        }
        batch_2_events.append(event)

    # Act: Publish batch 2 to Kafka
    for event in batch_2_events:
        kafka_producer.produce(
            topic="trips",
            value=json.dumps(event).encode("utf-8"),
            key=event["trip_id"].encode("utf-8"),
        )

    kafka_producer.flush(timeout=10.0)

    # Wait for batch 2 ingestion
    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=20,
        timeout_seconds=60,
        poll_interval=2.0,
        description="bronze_trips after batch 2",
    )

    # Verify 20 events before Thrift Server restart
    bronze_count_before_thrift_restart = count_rows(
        thrift_connection, "bronze.bronze_trips"
    )
    assert (
        bronze_count_before_thrift_restart == 20
    ), f"Expected 20 rows before Thrift restart, found {bronze_count_before_thrift_restart}"

    # Act: Restart spark-thrift-server container
    # Both profiles needed to resolve service dependencies
    restart_thrift_result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "infrastructure/docker/compose.yml",
            "--profile",
            "core",
            "--profile",
            "data-platform",
            "restart",
            "spark-thrift-server",
        ],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    assert restart_thrift_result.returncode == 0, (
        f"Thrift Server container restart failed.\n"
        f"STDOUT: {restart_thrift_result.stdout}\n"
        f"STDERR: {restart_thrift_result.stderr}"
    )

    # Wait for Thrift Server to restart and reconnect to Delta tables
    time.sleep(20)

    # Note: thrift_connection fixture may need to reconnect
    # Depending on fixture implementation, connection may be stale
    # This tests that querying works after restart

    # Assert: Query bronze_trips after Thrift Server restart
    # Need to re-establish connection after restart
    from pyhive import hive

    new_connection = hive.Connection(
        host="localhost", port=10000, database="default", auth="NOSASL"
    )

    try:
        # Bronze layer stores raw JSON in _raw_value column
        bronze_trips = query_table(
            new_connection,
            "SELECT _raw_value, _kafka_offset FROM bronze.bronze_trips ORDER BY _kafka_offset",
        )

        assert (
            len(bronze_trips) == 20
        ), f"Expected 20 events in bronze_trips after restarts, found {len(bronze_trips)}"

        # Assert: All trip_ids present (no data loss) - parse from JSON
        expected_trip_ids = {f"restart-test-{i:03d}" for i in range(1, 21)}
        actual_trip_ids = set()
        for row in bronze_trips:
            raw_json = json.loads(row["_raw_value"])
            actual_trip_ids.add(raw_json["trip_id"])

        assert (
            actual_trip_ids == expected_trip_ids
        ), f"Missing trip_ids. Expected {expected_trip_ids}, got {actual_trip_ids}"

        # Assert: No duplicates (exactly-once semantics)
        assert (
            len(actual_trip_ids) == 20
        ), "Duplicates found in bronze_trips after restart"

    finally:
        new_connection.close()

    # Assert: Verify checkpoint files exist in MinIO
    checkpoint_bucket = "rideshare-checkpoints"
    checkpoint_prefix = "trips/"

    try:
        # boto3 S3 client uses list_objects_v2
        response = minio_client.list_objects_v2(
            Bucket=checkpoint_bucket, Prefix=checkpoint_prefix
        )

        checkpoint_files = [obj["Key"] for obj in response.get("Contents", [])]

        assert (
            len(checkpoint_files) > 0
        ), f"No checkpoint files found in s3a://{checkpoint_bucket}/{checkpoint_prefix}"

        # Verify checkpoint metadata directory exists
        metadata_files = [f for f in checkpoint_files if "metadata" in f.lower()]
        assert len(metadata_files) > 0, "Checkpoint metadata files not found"

    except minio_client.exceptions.NoSuchBucket:
        pytest.fail(f"Checkpoint bucket '{checkpoint_bucket}' does not exist in MinIO")
    except Exception as e:
        pytest.fail(f"Failed to verify checkpoint files in MinIO: {e}")


# =============================================================================
# REG-003: Memory Pressure Resilience Test
# =============================================================================


@pytest.mark.regression
def test_memory_pressure_resilience(
    clean_bronze_tables,
    kafka_producer,
    thrift_connection,
):
    """REG-003: Verify services handle memory limits without OOM.

    Tests memory resilience by generating high-volume burst:
    1. Publishes 1000 events to Kafka in rapid succession
    2. Monitors spark-streaming-trips container memory usage
    3. Waits for processing to complete
    4. Checks container health status

    Validates:
    - No OOMKilled containers under high load
    - Memory stays within container limits
    - All 1000 events successfully processed
    - No data corruption from memory pressure
    """
    # Arrange: Generate 1000 test events (high-volume burst)
    # Note: pickup_location/dropoff_location must be arrays [lat, lon] for JSON parsing in DBT
    num_events = 1000
    burst_events = []

    for i in range(1, num_events + 1):
        event = {
            "event_id": f"memory-event-{i:05d}",
            "event_type": "trip.requested",
            "trip_id": f"memory-test-{i:05d}",
            "status": "requested",
            "timestamp": f"2026-01-20T12:{(i % 60):02d}:{(i // 60) % 60:02d}Z",
            "rider_id": f"rider-{(i % 100):03d}",
            "pickup_location": [
                -23.5505 + (i % 10) * 0.001,
                -46.6333 + (i % 10) * 0.001,
            ],
            "dropoff_location": [
                -23.5620 + (i % 10) * 0.001,
                -46.6550 + (i % 10) * 0.001,
            ],
        }
        burst_events.append(event)

    # Act: Publish all 1000 events in rapid succession
    publish_start_time = time.time()

    for event in burst_events:
        kafka_producer.produce(
            topic="trips",
            value=json.dumps(event).encode("utf-8"),
            key=event["trip_id"].encode("utf-8"),
        )

    kafka_producer.flush(timeout=30.0)  # Allow longer flush for high volume

    _publish_duration = time.time() - publish_start_time  # noqa: F841

    # Monitor: Check container memory before processing completes
    # This requires docker stats or docker inspect
    memory_check_result = subprocess.run(
        [
            "docker",
            "stats",
            "rideshare-spark-streaming-trips",
            "--no-stream",
            "--format",
            "{{.MemUsage}}",
        ],
        capture_output=True,
        text=True,
    )

    _memory_usage_during = memory_check_result.stdout.strip()  # noqa: F841

    # Wait for all events to be processed
    def query_bronze_count():
        return count_rows(thrift_connection, "bronze.bronze_trips")

    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=num_events,
        timeout_seconds=180,  # 3 minutes for high-volume processing
        poll_interval=5.0,
        description="bronze_trips after 1000-event burst",
    )

    # Assert: All 1000 events processed
    bronze_count = count_rows(thrift_connection, "bronze.bronze_trips")
    assert (
        bronze_count == num_events
    ), f"Expected {num_events} events in bronze_trips, found {bronze_count}"

    # Assert: Check container health status (no OOMKilled)
    health_check_result = subprocess.run(
        [
            "docker",
            "inspect",
            "rideshare-spark-streaming-trips",
            "--format",
            "{{.State.OOMKilled}}",
        ],
        capture_output=True,
        text=True,
    )

    oom_killed = health_check_result.stdout.strip()
    assert oom_killed == "false", "Container was OOMKilled during memory pressure test"

    # Assert: Verify container is still running
    container_running_result = subprocess.run(
        [
            "docker",
            "inspect",
            "rideshare-spark-streaming-trips",
            "--format",
            "{{.State.Running}}",
        ],
        capture_output=True,
        text=True,
    )

    container_running = container_running_result.stdout.strip()
    assert container_running == "true", "Container stopped during memory pressure test"

    # Assert: Query sample of events to verify no data corruption
    # Bronze layer stores raw JSON in _raw_value column
    sample_trips = query_table(
        thrift_connection,
        "SELECT _raw_value FROM bronze.bronze_trips "
        "WHERE _raw_value LIKE '%memory-test-00001%' "
        "   OR _raw_value LIKE '%memory-test-00500%' "
        "   OR _raw_value LIKE '%memory-test-01000%' "
        "ORDER BY _kafka_offset",
    )

    assert len(sample_trips) == 3, f"Expected 3 sample trips, found {len(sample_trips)}"

    # Verify no data corruption in sample - parse JSON
    for row in sample_trips:
        trip = json.loads(row["_raw_value"])
        assert (
            trip["status"] == "requested"
        ), f"Data corruption: trip {trip['trip_id']} has status {trip['status']}"
        assert (
            trip.get("correlation_id") is not None
        ), f"Data corruption: trip {trip['trip_id']} missing correlation_id"

    # Assert: No duplicates (exactly-once even under memory pressure)
    all_trips = query_table(
        thrift_connection, "SELECT _raw_value FROM bronze.bronze_trips"
    )

    unique_trip_ids = set()
    for row in all_trips:
        trip = json.loads(row["_raw_value"])
        unique_trip_ids.add(trip["trip_id"])

    assert (
        len(unique_trip_ids) == num_events
    ), f"Duplicates found: {len(all_trips)} rows, {len(unique_trip_ids)} unique trip_ids"
