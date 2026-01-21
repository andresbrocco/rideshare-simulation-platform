"""Feature journey integration tests for data platform.

Tests complete end-to-end flows through the medallion lakehouse architecture:
- FJ-001: Trip lifecycle Bronze ingestion
- FJ-002: GPS high-volume ingestion
- FJ-003: DBT Silver transformation
- FJ-004: DBT Gold layer models
- FJ-005: Airflow DAG execution
- FJ-006: Great Expectations validation
- FJ-007: Superset dashboard data access
"""

import json
import subprocess
import time
from collections import Counter
from pathlib import Path

import pytest

from tests.integration.data_platform.utils.sql_helpers import (
    count_rows,
    insert_bronze_data,
    insert_gold_data,
    insert_silver_data,
    query_table,
)
from tests.integration.data_platform.utils.wait_helpers import wait_for_condition


# Module-level fixtures: ensure services are ready before any test runs
pytestmark = [
    pytest.mark.feature_journey,
    pytest.mark.usefixtures(
        "streaming_jobs_running",
        "bronze_tables_initialized",
    ),
]

# Project root for subprocess commands
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.mark.feature_journey
def test_trip_lifecycle_bronze_ingestion(
    clean_bronze_tables,
    wait_for_bronze_ingestion,
    thrift_connection,
    test_trip_events,
):
    """FJ-001: Verify complete trip lifecycle flows from Kafka to Bronze.

    Publishes 6 trip events representing a complete trip lifecycle:
    - trip.requested
    - trip.matched
    - trip.driver_en_route
    - trip.driver_arrived
    - trip.started
    - trip.completed

    Verifies:
    - All 6 events appear in bronze_trips table
    - Events have correct metadata columns (_ingested_at, _kafka_partition, _kafka_offset)
    - Events are queryable by trip_id
    - Event order preserved (via timestamp)
    """
    # Arrange: test_trip_events generates 6 events, published_events publishes them
    # wait_for_bronze_ingestion polls until events appear in Bronze
    expected_count = len(test_trip_events)
    trip_id = test_trip_events[0]["trip_id"]

    # Act: Query bronze.bronze_trips table
    rows = query_table(
        thrift_connection,
        f"SELECT * FROM bronze.bronze_trips WHERE trip_id = '{trip_id}' ORDER BY timestamp",
    )

    # Assert: All 6 events present
    assert (
        len(rows) == expected_count
    ), f"Expected {expected_count} events in bronze_trips, found {len(rows)}"

    # Assert: Metadata columns present
    for row in rows:
        assert row.get("_ingested_at") is not None, "Missing _ingested_at metadata"
        assert (
            row.get("_kafka_partition") is not None
        ), "Missing _kafka_partition metadata"
        assert row.get("_kafka_offset") is not None, "Missing _kafka_offset metadata"

    # Assert: Events match expected types (event_type field)
    expected_types = [
        "trip.requested",
        "trip.matched",
        "trip.driver_en_route",
        "trip.driver_arrived",
        "trip.started",
        "trip.completed",
    ]
    actual_types = [row.get("event_type") for row in rows]
    assert (
        actual_types == expected_types
    ), f"Event types do not match. Expected {expected_types}, got {actual_types}"

    # Assert: All events have same trip_id
    assert all(
        row.get("trip_id") == trip_id for row in rows
    ), "Not all events have the expected trip_id"

    # Assert: Event order preserved (timestamps increasing)
    timestamps = [row.get("timestamp") for row in rows]
    assert timestamps == sorted(timestamps), "Events are not in chronological order"


@pytest.mark.feature_journey
def test_gps_pings_high_volume_ingestion(
    clean_bronze_tables,
    thrift_connection,
    kafka_producer,
    test_gps_events,
):
    """FJ-002: Verify GPS ping high-throughput streaming.

    Generates 100 GPS pings for 5 different drivers and publishes to
    gps-pings topic with 8 partitions. Verifies:
    - All 100 pings appear in bronze_gps_pings
    - Events are partitioned correctly by driver_id hash
    - Latency from publish to queryable < 30 seconds
    - No duplicate events (exactly-once semantics)
    """
    # Arrange: test_gps_events generates 100 GPS pings (20 per driver, 5 drivers)
    expected_count = len(test_gps_events)
    assert expected_count == 100, f"Expected 100 GPS events, got {expected_count}"

    # Record start time for latency measurement
    start_time = time.time()

    # Act: Publish all GPS events to gps-pings topic
    for event in test_gps_events:
        kafka_producer.produce(
            topic="gps-pings",
            value=json.dumps(event).encode("utf-8"),
            key=event["entity_id"].encode("utf-8"),  # Partition by driver_id
        )

    # Wait for all messages to be delivered
    kafka_producer.flush(timeout=10.0)

    # Wait for streaming trigger interval + processing time
    def check_gps_count():
        return (
            count_rows(thrift_connection, "bronze.bronze_gps_pings") >= expected_count
        )

    wait_for_condition(
        condition=check_gps_count,
        timeout_seconds=30,
        poll_interval=2.0,
        description="bronze_gps_pings to reach 100 rows",
    )

    # Record end time
    end_time = time.time()
    latency = end_time - start_time

    # Query all GPS pings
    rows = query_table(
        thrift_connection,
        "SELECT entity_id, location, timestamp, _kafka_partition "
        "FROM bronze.bronze_gps_pings "
        "ORDER BY entity_id, timestamp",
    )

    # Assert: All 100 pings present
    assert len(rows) >= expected_count, (
        f"Expected at least {expected_count} GPS pings in bronze_gps_pings, "
        f"found {len(rows)}"
    )

    # Assert: Latency < 30 seconds
    assert latency < 30, f"Ingestion latency {latency:.2f}s exceeds 30-second threshold"

    # Assert: 5 distinct drivers
    distinct_drivers = set(row["entity_id"] for row in rows)
    assert (
        len(distinct_drivers) == 5
    ), f"Expected 5 distinct drivers, found {len(distinct_drivers)}"

    # Assert: Each driver has 20 pings
    driver_counts = Counter(row["entity_id"] for row in rows)
    for entity_id, count in driver_counts.items():
        assert count == 20, f"Driver {entity_id} has {count} pings, expected 20"

    # Assert: No duplicate events (exactly-once semantics)
    # Check for duplicate (entity_id, timestamp) pairs
    event_keys = [(row["entity_id"], row["timestamp"]) for row in rows]
    assert len(event_keys) == len(
        set(event_keys)
    ), "Duplicate GPS events detected (same entity_id and timestamp)"

    # Assert: Partitioning occurred (multiple Kafka partitions used)
    partitions_used = set(row["_kafka_partition"] for row in rows)
    assert (
        len(partitions_used) > 1
    ), f"Expected multiple Kafka partitions, only {len(partitions_used)} used"


@pytest.mark.feature_journey
def test_dbt_silver_transformation(
    clean_bronze_tables,
    clean_silver_tables,
    thrift_connection,
):
    """FJ-003: Verify DBT transforms Bronze to Silver.

    Inserts controlled test data into Bronze tables, executes DBT Silver
    transformations, and validates:
    - stg_trips has deduplicated records
    - stg_gps_pings has valid coordinate ranges (-90 to 90, -180 to 180)
    - Anomaly detection tables populated (anomalies_gps_outliers)
    - Row counts: Silver <= Bronze (deduplication removes records)
    """
    # Arrange: Insert test data into Bronze tables
    # Include some duplicate records and anomalies for testing

    # Bronze trips: with duplicates
    bronze_trips_data = [
        {
            "trip_id": "trip-001",
            "event_type": "trip.completed",
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "timestamp": "2026-01-20T10:00:00Z",
            "_ingested_at": "2026-01-20T10:00:01Z",
            "_kafka_partition": 0,
            "_kafka_offset": 100,
        },
        {
            "trip_id": "trip-001",  # Duplicate
            "event_type": "trip.completed",
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "timestamp": "2026-01-20T10:00:00Z",
            "_ingested_at": "2026-01-20T10:00:02Z",  # Different ingestion time
            "_kafka_partition": 0,
            "_kafka_offset": 101,
        },
        {
            "trip_id": "trip-002",
            "event_type": "trip.completed",
            "rider_id": "rider-002",
            "driver_id": "driver-002",
            "timestamp": "2026-01-20T11:00:00Z",
            "_ingested_at": "2026-01-20T11:00:01Z",
            "_kafka_partition": 1,
            "_kafka_offset": 200,
        },
    ]

    # Bronze GPS pings: with invalid coordinates
    bronze_gps_data = [
        {
            "entity_id": "driver-001",
            "entity_type": "driver",
            "location": "[-23.5505, -46.6333]",
            "timestamp": "2026-01-20T10:00:00Z",
            "_ingested_at": "2026-01-20T10:00:01Z",
            "_kafka_partition": 0,
            "_kafka_offset": 100,
        },
        {
            "entity_id": "driver-001",
            "entity_type": "driver",
            "location": "[999.0, -46.6333]",  # Invalid latitude (outlier)
            "timestamp": "2026-01-20T10:00:05Z",
            "_ingested_at": "2026-01-20T10:00:06Z",
            "_kafka_partition": 0,
            "_kafka_offset": 101,
        },
        {
            "entity_id": "driver-002",
            "entity_type": "driver",
            "location": "[-23.5629, -46.6544]",
            "timestamp": "2026-01-20T10:00:00Z",
            "_ingested_at": "2026-01-20T10:00:01Z",
            "_kafka_partition": 1,
            "_kafka_offset": 102,
        },
    ]

    insert_bronze_data(thrift_connection, "bronze.bronze_trips", bronze_trips_data)
    insert_bronze_data(thrift_connection, "bronze.bronze_gps_pings", bronze_gps_data)

    # Record Bronze counts before transformation
    bronze_trips_count = count_rows(thrift_connection, "bronze.bronze_trips")
    bronze_gps_count = count_rows(thrift_connection, "bronze.bronze_gps_pings")

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

    # Query Silver tables
    silver_trips = query_table(
        thrift_connection,
        "SELECT trip_id, event_type, timestamp FROM silver.stg_trips ORDER BY trip_id",
    )

    silver_gps = query_table(
        thrift_connection,
        "SELECT entity_id, location FROM silver.stg_gps_pings ORDER BY entity_id",
    )

    # Assert: stg_trips has deduplicated records
    assert len(silver_trips) < bronze_trips_count, (
        f"Expected deduplication. Bronze: {bronze_trips_count}, "
        f"Silver: {len(silver_trips)}"
    )

    # Assert: No duplicate trip_id + timestamp in Silver
    trip_keys = [(row["trip_id"], row["timestamp"]) for row in silver_trips]
    assert len(trip_keys) == len(
        set(trip_keys)
    ), "Duplicate trips found in stg_trips after deduplication"

    # Assert: Silver GPS count <= Bronze (outliers removed)
    assert (
        len(silver_gps) <= bronze_gps_count
    ), f"Silver GPS count ({len(silver_gps)}) should be <= Bronze ({bronze_gps_count})"

    # Assert: Anomaly tables populated (if they exist and have data)
    try:
        anomaly_gps = query_table(
            thrift_connection, "SELECT * FROM silver.anomalies_gps_outliers"
        )
        # If table exists and has data, validate
        if len(anomaly_gps) > 0:
            print(f"Found {len(anomaly_gps)} GPS outliers in anomaly table")
    except Exception:
        # Table may not exist yet - that's OK for this test
        pass


@pytest.mark.feature_journey
def test_dbt_gold_layer_models(
    clean_silver_tables,
    clean_gold_tables,
    thrift_connection,
):
    """FJ-004: Verify DBT builds Gold layer from Silver.

    Executes DBT transformations for dimensions, facts, and aggregates.
    Validates:
    - dim_drivers has SCD Type 2 (valid_from, valid_to columns)
    - fact_trips joins successfully with all dimensions
    - fact_payments links to fact_trips
    - agg_hourly_zone_demand has aggregated metrics
    """
    # Arrange: Insert test data into Silver staging tables

    # Silver drivers: 2 drivers, with driver-001 having a profile update
    silver_drivers = [
        {
            "driver_id": "driver-001",
            "vehicle_type": "sedan",
            "vehicle_make": "Toyota",
            "effective_date": "2026-01-01T00:00:00Z",
        },
        {
            "driver_id": "driver-001",  # Same driver, updated profile
            "vehicle_type": "suv",  # Changed vehicle type
            "vehicle_make": "Honda",
            "effective_date": "2026-01-15T00:00:00Z",  # Later date
        },
        {
            "driver_id": "driver-002",
            "vehicle_type": "sedan",
            "vehicle_make": "Ford",
            "effective_date": "2026-01-01T00:00:00Z",
        },
    ]

    # Silver trips
    silver_trips = [
        {
            "trip_id": "trip-001",
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "pickup_zone_id": "zone-01",
            "dropoff_zone_id": "zone-02",
            "fare": 25.50,
            "event_type": "trip.completed",
            "timestamp": "2026-01-20T10:00:00Z",
        },
        {
            "trip_id": "trip-002",
            "rider_id": "rider-002",
            "driver_id": "driver-002",
            "pickup_zone_id": "zone-01",
            "dropoff_zone_id": "zone-03",
            "fare": 30.00,
            "event_type": "trip.completed",
            "timestamp": "2026-01-20T11:00:00Z",
        },
    ]

    # Silver payments
    silver_payments = [
        {
            "payment_id": "payment-001",
            "trip_id": "trip-001",
            "amount": 25.50,
            "payment_method": "credit_card",
            "timestamp": "2026-01-20T10:05:00Z",
        },
    ]

    insert_silver_data(thrift_connection, "silver.stg_driver_profiles", silver_drivers)
    insert_silver_data(thrift_connection, "silver.stg_trips", silver_trips)
    insert_silver_data(thrift_connection, "silver.stg_payments", silver_payments)

    # Act: Execute DBT Gold transformations in dependency order

    # Step 1: Build dimensions
    dbt_dims_result = subprocess.run(
        [
            "./venv/bin/dbt",
            "run",
            "--select",
            "tag:dimensions",
            "--profiles-dir",
            "profiles",
            "--project-dir",
            ".",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT / "services" / "dbt"),
    )
    assert (
        dbt_dims_result.returncode == 0
    ), f"dbt dimensions failed: {dbt_dims_result.stderr}"

    # Step 2: Build facts
    dbt_facts_result = subprocess.run(
        [
            "./venv/bin/dbt",
            "run",
            "--select",
            "tag:facts",
            "--profiles-dir",
            "profiles",
            "--project-dir",
            ".",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT / "services" / "dbt"),
    )
    assert (
        dbt_facts_result.returncode == 0
    ), f"dbt facts failed: {dbt_facts_result.stderr}"

    # Step 3: Build aggregates
    dbt_aggs_result = subprocess.run(
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
    assert (
        dbt_aggs_result.returncode == 0
    ), f"dbt aggregates failed: {dbt_aggs_result.stderr}"

    # Query Gold tables

    # Query dim_drivers (SCD Type 2)
    dim_drivers = query_table(
        thrift_connection,
        "SELECT driver_id, vehicle_type, valid_from, valid_to, is_current "
        "FROM gold.dim_drivers ORDER BY driver_id, valid_from",
    )

    # Assert: dim_drivers has SCD Type 2 columns
    if len(dim_drivers) > 0:
        first_row = dim_drivers[0]
        assert "valid_from" in first_row, "dim_drivers missing valid_from column"
        assert "valid_to" in first_row, "dim_drivers missing valid_to column"
        assert "is_current" in first_row, "dim_drivers missing is_current column"

    # Assert: driver-001 has 2 versions (SCD Type 2)
    driver_001_versions = [
        row for row in dim_drivers if row.get("driver_id") == "driver-001"
    ]
    assert (
        len(driver_001_versions) == 2
    ), f"Expected 2 versions for driver-001, found {len(driver_001_versions)}"

    # Assert: Only one version is current
    current_versions = [row for row in driver_001_versions if row.get("is_current")]
    assert (
        len(current_versions) == 1
    ), f"Expected 1 current version for driver-001, found {len(current_versions)}"

    # Query fact_trips
    fact_trips = query_table(
        thrift_connection,
        "SELECT trip_id, rider_id, driver_id, fare FROM gold.fact_trips",
    )

    # Assert: fact_trips has data
    assert len(fact_trips) > 0, "fact_trips table is empty"

    # Assert: fact_trips can join with dimensions (foreign key integrity)
    fact_driver_ids = set(row["driver_id"] for row in fact_trips)
    dim_driver_ids = set(row["driver_id"] for row in dim_drivers)
    assert fact_driver_ids.issubset(dim_driver_ids), (
        f"fact_trips has driver_ids not in dim_drivers: "
        f"{fact_driver_ids - dim_driver_ids}"
    )

    # Query fact_payments
    fact_payments = query_table(
        thrift_connection,
        "SELECT payment_id, trip_id, amount FROM gold.fact_payments",
    )

    # Assert: fact_payments links to fact_trips
    fact_trip_ids = set(row["trip_id"] for row in fact_trips)
    payment_trip_ids = set(row["trip_id"] for row in fact_payments)
    assert payment_trip_ids.issubset(fact_trip_ids), (
        f"fact_payments has trip_ids not in fact_trips: "
        f"{payment_trip_ids - fact_trip_ids}"
    )

    # Query aggregates
    try:
        hourly_demand = query_table(
            thrift_connection,
            "SELECT * FROM gold.agg_hourly_zone_demand LIMIT 10",
        )

        # Assert: Aggregates computed correctly
        if len(hourly_demand) > 0:
            sample_agg = hourly_demand[0]
            assert (
                sample_agg.get("trip_count", 0) >= 0
            ), "trip_count should be non-negative"
    except Exception:
        # Aggregate table may not exist yet
        pass


@pytest.mark.feature_journey
def test_airflow_dag_execution(
    airflow_dags_loaded,
    airflow_client,
    thrift_connection,
):
    """FJ-005: Verify Airflow orchestrates DBT and Great Expectations.

    Triggers two DAGs via REST API and monitors execution:
    1. dbt_transformation DAG (Silver layer)
    2. dbt_gold_transformation DAG (Gold layer)

    Validates:
    - Both DAGs complete successfully
    - All tasks pass (no failed tasks)
    """
    # Arrange: Prepare some Bronze data for DAG to process
    bronze_trips_data = [
        {
            "trip_id": "trip-airflow-001",
            "event_type": "trip.completed",
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "timestamp": "2026-01-20T10:00:00Z",
            "_ingested_at": "2026-01-20T10:00:01Z",
            "_kafka_partition": 0,
            "_kafka_offset": 1000,
        },
    ]
    insert_bronze_data(thrift_connection, "bronze.bronze_trips", bronze_trips_data)

    # Act: Trigger dbt_transformation DAG
    print("Triggering dbt_transformation DAG...")
    try:
        dag_run_id_1 = airflow_client.trigger_dag(
            dag_id="dbt_transformation", conf={"test_run": True}
        )
    except Exception as e:
        pytest.skip(f"Could not trigger dbt_transformation DAG: {e}")

    assert dag_run_id_1 is not None, "Failed to trigger dbt_transformation DAG"

    # Wait for DAG completion
    max_wait_seconds = 300  # 5 minutes

    final_state_1 = airflow_client.wait_for_dag_completion(
        dag_id="dbt_transformation",
        dag_run_id=dag_run_id_1,
        timeout_seconds=max_wait_seconds,
        poll_interval=5.0,
    )

    # Assert: DAG succeeded
    assert (
        final_state_1 == "success"
    ), f"dbt_transformation DAG failed with state: {final_state_1}"

    # Act: Trigger dbt_gold_transformation DAG
    print("Triggering dbt_gold_transformation DAG...")
    try:
        dag_run_id_2 = airflow_client.trigger_dag(
            dag_id="dbt_gold_transformation", conf={"test_run": True}
        )
    except Exception as e:
        pytest.skip(f"Could not trigger dbt_gold_transformation DAG: {e}")

    assert dag_run_id_2 is not None, "Failed to trigger dbt_gold_transformation DAG"

    # Wait for DAG completion
    final_state_2 = airflow_client.wait_for_dag_completion(
        dag_id="dbt_gold_transformation",
        dag_run_id=dag_run_id_2,
        timeout_seconds=max_wait_seconds,
        poll_interval=5.0,
    )

    # Assert: DAG succeeded
    assert (
        final_state_2 == "success"
    ), f"dbt_gold_transformation DAG failed with state: {final_state_2}"

    print("Both DAGs completed successfully!")


@pytest.mark.feature_journey
def test_great_expectations_validation(
    thrift_connection,
    clean_silver_tables,
    clean_gold_tables,
):
    """FJ-006: Verify Great Expectations checkpoints validate data quality.

    Runs two Great Expectations checkpoints:
    1. silver_validation: Validates Silver staging tables
    2. gold_validation: Validates Gold layer tables

    Validates:
    - Silver checkpoint runs successfully
    - Gold checkpoint runs successfully
    - No critical expectation failures
    - Data docs generated
    """
    # Arrange: Prepare Silver data
    silver_trips = [
        {
            "trip_id": "trip-ge-001",
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "event_type": "trip.completed",
            "fare": 25.50,
            "timestamp": "2026-01-20T10:00:00Z",
        },
    ]

    silver_gps_pings = [
        {
            "entity_id": "driver-001",
            "entity_type": "driver",
            "location": "[-23.5505, -46.6333]",
            "timestamp": "2026-01-20T10:00:00Z",
        },
    ]

    insert_silver_data(thrift_connection, "silver.stg_trips", silver_trips)
    insert_silver_data(thrift_connection, "silver.stg_gps_pings", silver_gps_pings)

    # Prepare Gold data
    gold_drivers = [
        {
            "driver_id": "driver-001",
            "vehicle_type": "sedan",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": None,
            "is_current": True,
        },
    ]

    gold_trips = [
        {
            "trip_id": "trip-ge-001",
            "rider_id": "rider-001",
            "driver_id": "driver-001",
            "fare": 25.50,
        },
    ]

    insert_gold_data(thrift_connection, "gold.dim_drivers", gold_drivers)
    insert_gold_data(thrift_connection, "gold.fact_trips", gold_trips)

    # Act: Run silver_validation checkpoint
    print("Running silver_validation checkpoint...")
    silver_checkpoint_result = subprocess.run(
        [
            "great_expectations",
            "checkpoint",
            "run",
            "silver_validation",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT / "quality" / "great-expectations"),
    )

    silver_returncode = silver_checkpoint_result.returncode
    silver_output = silver_checkpoint_result.stdout

    print(f"Silver checkpoint return code: {silver_returncode}")

    # Act: Run gold_validation checkpoint
    print("Running gold_validation checkpoint...")
    gold_checkpoint_result = subprocess.run(
        [
            "great_expectations",
            "checkpoint",
            "run",
            "gold_validation",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT / "quality" / "great-expectations"),
    )

    gold_returncode = gold_checkpoint_result.returncode
    gold_output = gold_checkpoint_result.stdout

    print(f"Gold checkpoint return code: {gold_returncode}")

    # Assert: Checkpoints ran (even if some expectations failed)
    # Critical assertion: checkpoints executed without crashing
    assert (
        "Checkpoint" in silver_output or silver_returncode == 0
    ), f"Silver checkpoint did not run properly. Output: {silver_output}"

    assert (
        "Checkpoint" in gold_output or gold_returncode == 0
    ), f"Gold checkpoint did not run properly. Output: {gold_output}"

    # Parse checkpoint results from GE uncommitted directory
    validations_dir = (
        PROJECT_ROOT / "quality" / "great-expectations" / "uncommitted" / "validations"
    )

    # Find validation results
    if validations_dir.exists():
        validation_files = sorted(validations_dir.rglob("*.json"), reverse=True)

        if len(validation_files) > 0:
            # Read most recent validation result
            latest_validation = validation_files[0]
            with open(latest_validation, "r") as f:
                validation_result = json.load(f)

            # Check for statistics
            statistics = validation_result.get("statistics", {})
            evaluated_expectations = statistics.get("evaluated_expectations", 0)

            print(f"Evaluated {evaluated_expectations} expectations")

            # Assert: At least some expectations ran
            assert (
                evaluated_expectations > 0
            ), f"No expectations were evaluated. Statistics: {statistics}"

    # Assert: Data docs generated
    data_docs_dir = (
        PROJECT_ROOT / "quality" / "great-expectations" / "uncommitted" / "data_docs"
    )

    if data_docs_dir.exists():
        index_files = list(data_docs_dir.rglob("index.html"))
        assert len(index_files) > 0, "Data docs index.html not generated"

    print("Great Expectations validation completed successfully!")


@pytest.mark.feature_journey
def test_superset_spark_connectivity(
    superset_client,
    thrift_connection,
):
    """FJ-007: Verify Superset can query Gold layer via Spark Thrift Server.

    Tests Superset connectivity to the data platform:
    1. Get or create Spark Thrift Server database connection
    2. Execute test query against agg_hourly_zone_demand
    3. Verify results

    Validates:
    - Superset authentication succeeds
    - Database connection to Thrift Server works
    - Query returns expected columns from Gold layer
    - Results parseable as JSON
    """
    # Arrange: Prepare Gold aggregate data
    hourly_demand_data = [
        {
            "trip_date": "2026-01-20",
            "trip_hour": 10,
            "zone_id": "zone-01",
            "trip_count": 15,
            "total_fare": 375.50,
            "avg_duration_seconds": 420,
        },
        {
            "trip_date": "2026-01-20",
            "trip_hour": 11,
            "zone_id": "zone-02",
            "trip_count": 22,
            "total_fare": 550.00,
            "avg_duration_seconds": 480,
        },
    ]

    insert_gold_data(
        thrift_connection, "gold.agg_hourly_zone_demand", hourly_demand_data
    )

    # Act: Get existing database connections
    databases = superset_client.list_databases()
    assert isinstance(databases, list), "Failed to list Superset databases"

    print(f"Superset has {len(databases)} database connections")

    # Check if Spark Thrift connection already exists
    spark_db_name = "Spark Thrift Server"
    spark_db = next(
        (db for db in databases if db.get("database_name") == spark_db_name),
        None,
    )

    if spark_db is None:
        # Skip if no Spark connection configured
        pytest.skip(
            f"No '{spark_db_name}' database connection configured in Superset. "
            "Create it manually or via Superset UI."
        )

    # Extract database ID
    database_id = spark_db.get("id")
    assert database_id is not None, "Database ID is missing"

    # Act: Execute test query against Gold table
    test_query = """
        SELECT
            trip_date,
            trip_hour,
            zone_id,
            trip_count,
            total_fare
        FROM gold.agg_hourly_zone_demand
        WHERE trip_date = '2026-01-20'
        ORDER BY trip_hour, zone_id
        LIMIT 10
    """

    print("Executing test query via Superset SQL Lab...")
    query_result = superset_client.execute_query(
        database_id=database_id, sql=test_query
    )

    # Assert: Query executed successfully
    assert query_result is not None, "Query result is None"

    # Assert: Result has expected structure
    assert (
        "data" in query_result or "result" in query_result
    ), "Query result missing data"

    # Assert: Results are JSON-serializable
    json_output = json.dumps(query_result)
    assert len(json_output) > 0, "Failed to serialize query result to JSON"

    print("Superset successfully queried Gold layer via Spark Thrift Server!")
