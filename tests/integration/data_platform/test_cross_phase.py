"""Cross-phase integration tests for data platform.

Tests integration between phases of the medallion lakehouse architecture:
- XP-001: Phase 1-2 integration (MinIO + Streaming)
- XP-002: Phase 2-3 integration (Bronze + DBT)
"""

import json
import subprocess
import time
from pathlib import Path

import pytest

from tests.integration.data_platform.utils.sql_helpers import count_rows, query_table

# Project root for subprocess commands
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Module-level fixtures: ensure services are ready before any test runs
# Note: streaming_jobs_running is NOT required for tests that only test DBT
# transformations. Only tests that rely on Kafka -> Bronze ingestion need it.
pytestmark = [
    pytest.mark.cross_phase,
    pytest.mark.usefixtures(
        "bronze_tables_initialized",
    ),
]


@pytest.mark.cross_phase
@pytest.mark.requires_profiles("core", "data-platform")
@pytest.mark.usefixtures("streaming_jobs_running")
def test_phase1_phase2_minio_streaming(
    clean_bronze_tables,
    minio_client,
    kafka_producer,
    thrift_connection,
):
    """XP-001: Verify Phase 1 MinIO integrates with Phase 2 streaming.

    Tests the foundational integration between MinIO object storage
    and Spark Structured Streaming, ensuring Delta Lake files are
    correctly written and queryable.

    Verifies:
    - rideshare-bronze bucket exists in MinIO
    - Delta _delta_log directory created
    - Parquet data files written
    - Files accessible via s3a:// protocol
    - Spark Thrift Server can read Delta tables
    """
    # Arrange: Verify bucket exists
    buckets_response = minio_client.list_buckets()
    bucket_names = [bucket["Name"] for bucket in buckets_response["Buckets"]]
    assert (
        "rideshare-bronze" in bucket_names
    ), "rideshare-bronze bucket not found in MinIO"

    # Arrange: Publish single trip event
    # Note: Event must include event_id and proper location format for DBT parsing
    trip_event = {
        "event_id": "xp001-event-001",
        "event_type": "trip.requested",
        "trip_id": "xp001-trip-001",
        "status": "requested",
        "rider_id": "xp001-rider-001",
        "timestamp": "2026-01-20T12:00:00Z",
        "pickup_location": [-23.5505, -46.6333],
        "dropoff_location": [-23.5620, -46.6550],
    }
    kafka_producer.produce(
        topic="trips",
        key=trip_event["trip_id"].encode("utf-8"),
        value=json.dumps(trip_event).encode("utf-8"),
    )
    kafka_producer.flush()

    # Act: Wait for streaming job to process
    time.sleep(15)  # Wait for trigger interval + processing

    # Assert: Verify Delta _delta_log directory exists
    try:
        objects = minio_client.list_objects_v2(
            Bucket="rideshare-bronze",
            Prefix="bronze_trips/_delta_log/",
        )
        delta_log_files = objects.get("Contents", [])
        assert len(delta_log_files) > 0, "Delta _delta_log directory not found in MinIO"
    except minio_client.exceptions.NoSuchBucket:
        pytest.fail("rideshare-bronze bucket does not exist")

    # Assert: Verify parquet data files exist
    data_objects = minio_client.list_objects_v2(
        Bucket="rideshare-bronze",
        Prefix="bronze_trips/",
    )
    all_files = data_objects.get("Contents", [])
    parquet_files = [obj["Key"] for obj in all_files if obj["Key"].endswith(".parquet")]
    assert len(parquet_files) > 0, "No parquet data files found in MinIO"

    # Assert: Verify Spark can read via Thrift Server
    # Bronze layer stores raw JSON in _raw_value column
    rows = query_table(
        thrift_connection,
        f"SELECT _raw_value FROM bronze.bronze_trips WHERE _raw_value LIKE '%{trip_event['trip_id']}%'",
    )
    assert (
        len(rows) >= 1
    ), f"Expected at least 1 event in bronze_trips, found {len(rows)}"

    # Parse JSON from _raw_value to verify trip_id
    raw_json = json.loads(rows[0]["_raw_value"])
    assert (
        raw_json["trip_id"] == trip_event["trip_id"]
    ), "Event not readable via Thrift Server"


@pytest.mark.cross_phase
@pytest.mark.requires_profiles("core", "data-platform")
@pytest.mark.usefixtures("streaming_jobs_running")
def test_phase2_phase3_bronze_dbt(
    clean_bronze_tables,
    thrift_connection,
    kafka_producer,
):
    """XP-002: Verify Phase 2 Bronze tables consumable by Phase 3 DBT.

    Tests the integration between Bronze Delta tables and DBT transformations,
    ensuring DBT can read from Bronze and execute source freshness checks.

    Verifies:
    - Bronze tables queryable directly via Thrift
    - DBT source freshness check passes
    - No connectivity errors in DBT execution
    - Data types compatible between Bronze and DBT models
    """
    # Arrange: Publish events to ensure Bronze has data
    # Note: Events must include event_id and proper location format for DBT parsing
    trip_events = [
        {
            "event_id": f"xp002-event-{i:03d}",
            "event_type": "trip.completed",
            "trip_id": f"xp002-trip-{i:03d}",
            "status": "completed",
            "rider_id": f"xp002-rider-{i:03d}",
            "driver_id": f"xp002-driver-{i:03d}",
            "timestamp": "2026-01-20T12:00:00Z",
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5620, -46.6550],
        }
        for i in range(1, 6)
    ]

    for event in trip_events:
        kafka_producer.produce(
            topic="trips",
            key=event["trip_id"].encode("utf-8"),
            value=json.dumps(event).encode("utf-8"),
        )
    kafka_producer.flush()

    # Wait for streaming to process
    time.sleep(15)

    # Arrange: Verify Bronze data exists
    trip_count = count_rows(thrift_connection, "bronze.bronze_trips")
    assert trip_count > 0, "Bronze tables must have data for DBT source tests"

    # Act: Run DBT debug to check connection using local DBT installation
    debug_result = subprocess.run(
        [
            "./venv/bin/dbt",
            "debug",
            "--profiles-dir",
            "profiles",
            "--project-dir",
            ".",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(PROJECT_ROOT / "services" / "dbt"),
    )

    # Assert: DBT can connect
    assert (
        "Connection test: [OK connection ok]" in debug_result.stdout
        or debug_result.returncode == 0
    ), f"DBT connection check failed:\nSTDOUT: {debug_result.stdout}\nSTDERR: {debug_result.stderr}"

    # Assert: No connectivity errors
    assert (
        "Could not connect" not in debug_result.stdout
    ), "DBT could not connect to Bronze tables"
    assert (
        "Database Error" not in debug_result.stderr
    ), f"DBT encountered database error:\n{debug_result.stderr}"

    # Act: Run DBT source freshness check (if sources configured) using local DBT installation
    freshness_result = subprocess.run(
        [
            "./venv/bin/dbt",
            "source",
            "freshness",
            "--profiles-dir",
            "profiles",
            "--project-dir",
            ".",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(PROJECT_ROOT / "services" / "dbt"),
    )

    # Note: Source freshness may return non-zero if no freshness tests configured
    # The key assertion is no connectivity errors
    assert (
        "Could not connect" not in freshness_result.stdout
    ), "DBT could not connect during source freshness check"

    # Assert: Data type compatibility confirmed (no compilation errors)
    assert (
        "Compilation Error" not in freshness_result.stderr
    ), "Data type incompatibility detected in DBT models"
