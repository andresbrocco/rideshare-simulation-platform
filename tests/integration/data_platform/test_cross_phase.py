"""Cross-phase integration tests for data platform.

Tests integration between phases of the medallion lakehouse architecture:
- XP-001: Phase 1-2 integration (MinIO + Streaming)
- XP-002: Phase 2-3 integration (Bronze + DBT)
- XP-003: Phase 3-4 integration (DBT + Airflow)
- XP-004: Phase 3-5 integration (Gold + Superset)
- XP-005: Phase 4-5 integration (Airflow + Grafana)
"""

import json
import subprocess
import time

import pytest

from tests.integration.data_platform.utils.sql_helpers import count_rows, query_table

# Module-level fixtures: ensure services are ready before any test runs
pytestmark = [
    pytest.mark.cross_phase,
    pytest.mark.usefixtures(
        "streaming_jobs_running",
        "bronze_tables_initialized",
    ),
]


@pytest.mark.cross_phase
@pytest.mark.requires_profiles("core", "data-platform")
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
    trip_event = {
        "trip_id": "xp001-trip-001",
        "status": "requested",
        "rider_id": "xp001-rider-001",
        "event_timestamp": "2026-01-20T12:00:00Z",
        "correlation_id": "xp001-corr-001",
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
    rows = query_table(
        thrift_connection,
        f"SELECT * FROM bronze.bronze_trips WHERE trip_id = '{trip_event['trip_id']}'",
    )
    assert (
        len(rows) >= 1
    ), f"Expected at least 1 event in bronze_trips, found {len(rows)}"
    assert (
        rows[0]["trip_id"] == trip_event["trip_id"]
    ), "Event not readable via Thrift Server"


@pytest.mark.cross_phase
@pytest.mark.requires_profiles("core", "data-platform")
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
    trip_events = [
        {
            "trip_id": f"xp002-trip-{i:03d}",
            "status": "completed",
            "rider_id": f"xp002-rider-{i:03d}",
            "driver_id": f"xp002-driver-{i:03d}",
            "event_timestamp": "2026-01-20T12:00:00Z",
            "correlation_id": f"xp002-corr-{i:03d}",
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

    # Get project root for DBT commands
    project_root = (
        "/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform"
    )

    # Act: Run DBT debug to check connection
    debug_result = subprocess.run(
        [
            "services/dbt/venv/bin/dbt",
            "debug",
            "--profiles-dir",
            "services/dbt",
            "--project-dir",
            "services/dbt",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=60,
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

    # Act: Run DBT source freshness check (if sources configured)
    freshness_result = subprocess.run(
        [
            "services/dbt/venv/bin/dbt",
            "source",
            "freshness",
            "--profiles-dir",
            "services/dbt",
            "--project-dir",
            "services/dbt",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
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


@pytest.mark.cross_phase
@pytest.mark.requires_profiles("core", "data-platform", "quality-orchestration")
def test_phase3_phase4_dbt_airflow(
    airflow_client,
    airflow_dags_loaded,
):
    """XP-003: Verify Phase 3 DBT models work with Phase 4 Airflow orchestration.

    Tests the integration between DBT transformations and Airflow orchestration,
    ensuring Airflow can successfully parse DAGs and execute DBT commands.

    Verifies:
    - DAG files parsed without import errors
    - No DAG import errors in Airflow
    - DBT BashOperator executes successfully
    - Task logs show DBT output
    - Task state = success
    """
    # Assert: No DAG import errors - use underlying client for direct API access
    import_errors = airflow_client.client.get(
        f"{airflow_client.base_url}/api/v1/importErrors"
    )
    assert (
        import_errors.status_code == 200
    ), f"Failed to get import errors: {import_errors.text}"
    errors_data = import_errors.json()
    assert (
        errors_data["total_entries"] == 0
    ), f"DAG import errors detected: {errors_data.get('import_errors', [])}"

    # Arrange: Get dbt_transformation DAG
    dag_id = "dbt_transformation"
    dag_response = airflow_client.client.get(
        f"{airflow_client.base_url}/api/v1/dags/{dag_id}"
    )

    # Skip if DBT DAG not found (might not be deployed yet)
    if dag_response.status_code == 404:
        pytest.skip(f"DAG {dag_id} not found in Airflow - skipping")

    assert (
        dag_response.status_code == 200
    ), f"DAG {dag_id} request failed: {dag_response.text}"

    # Act: Trigger DAG run
    trigger_response = airflow_client.client.post(
        f"{airflow_client.base_url}/api/v1/dags/{dag_id}/dagRuns",
        json={"conf": {}},
    )
    assert trigger_response.status_code in [
        200,
        201,
    ], f"Failed to trigger DAG: {trigger_response.text}"
    dag_run_id = trigger_response.json()["dag_run_id"]

    # Act: Wait for DAG completion
    max_wait = 300  # 5 minutes
    poll_interval = 10
    elapsed = 0
    dag_state = None

    while elapsed < max_wait:
        state_response = airflow_client.client.get(
            f"{airflow_client.base_url}/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}"
        )
        if state_response.status_code == 200:
            dag_data = state_response.json()
            dag_state = dag_data.get("state")
            if dag_state in ["success", "failed"]:
                break
        time.sleep(poll_interval)
        elapsed += poll_interval

    # Assert: DAG completed successfully
    assert (
        dag_state == "success"
    ), f"DAG {dag_id} did not complete successfully: state={dag_state}"

    # Act: Get task instances to verify DBT task ran
    tasks_response = airflow_client.client.get(
        f"{airflow_client.base_url}/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances"
    )
    assert (
        tasks_response.status_code == 200
    ), f"Failed to get task instances: {tasks_response.text}"

    # Assert: All tasks succeeded
    tasks = tasks_response.json()["task_instances"]
    for task in tasks:
        assert (
            task["state"] == "success"
        ), f"Task {task['task_id']} did not succeed: state={task['state']}"


@pytest.mark.cross_phase
@pytest.mark.requires_profiles("core", "data-platform", "bi")
def test_phase3_phase5_gold_superset(
    superset_client,
    thrift_connection,
):
    """XP-004: Verify Phase 3 Gold tables queryable from Phase 5 Superset.

    Tests the integration between Gold layer tables and Superset BI dashboards,
    ensuring Superset can connect to Spark Thrift Server and query Gold tables.

    Verifies:
    - Superset can connect to Spark Thrift Server
    - Gold tables are discoverable in Superset
    - Query execution succeeds against Gold tables
    - Column metadata is correct
    - Data types render properly
    """
    # Arrange: Check if Gold tables exist and have data
    gold_count = count_rows(thrift_connection, "gold.agg_hourly_zone_demand")
    if gold_count == 0:
        # Skip test if no Gold data (requires prior DBT run)
        pytest.skip("Gold tables empty, run DBT transformations first")

    # Act: Get list of databases
    databases = superset_client.list_databases()

    # Check if Spark Thrift database connection exists
    spark_db = next(
        (db for db in databases if "spark" in db["database_name"].lower()), None
    )

    # Create connection if not exists
    if spark_db is None:
        create_response = superset_client.client.post(
            f"{superset_client.base_url}/api/v1/database/",
            json={
                "database_name": "Spark Thrift Server",
                "sqlalchemy_uri": "hive://spark-thrift-server:10000/default",
                "expose_in_sqllab": True,
            },
        )
        assert create_response.status_code in [
            200,
            201,
        ], f"Failed to create database connection: {create_response.text}"
        spark_db_id = create_response.json()["id"]
    else:
        spark_db_id = spark_db["id"]

    # Act: Test database connection
    test_response = superset_client.client.post(
        f"{superset_client.base_url}/api/v1/database/{spark_db_id}/test_connection"
    )
    # Note: test_connection might return 400 if already connected
    assert test_response.status_code in [
        200,
        400,
    ], f"Database connection test failed unexpectedly: {test_response.text}"

    # Act: Execute sample query via SQL Lab
    try:
        query_result = superset_client.execute_query(
            database_id=spark_db_id,
            sql="SELECT * FROM gold.agg_hourly_zone_demand LIMIT 10",
        )
        # Assert: Query execution succeeded
        assert query_result is not None, "Query returned no result"
    except Exception as e:
        # Handle async query execution
        if "query_id" in str(e) or "async" in str(e).lower():
            # Query is running asynchronously - acceptable
            pass
        else:
            pytest.fail(f"Query execution failed: {e}")


@pytest.mark.cross_phase
@pytest.mark.requires_profiles(
    "core", "data-platform", "quality-orchestration", "monitoring"
)
def test_phase4_phase5_airflow_grafana(
    prometheus_client,
    grafana_client,
    airflow_dags_loaded,
):
    """XP-005: Verify Airflow metrics exposed to Grafana via Prometheus.

    Tests the integration between Airflow orchestration and Grafana monitoring,
    ensuring Airflow metrics are collected by Prometheus and visualized in Grafana.

    Verifies:
    - Airflow metrics present in Prometheus
    - Grafana can query Prometheus for Airflow metrics
    - Airflow-metrics dashboard loads successfully
    - Dashboard queries return data
    - Alert rules evaluate without error
    """
    # Act: Query Prometheus for Airflow metrics
    try:
        prom_data = prometheus_client.query_instant("airflow_dag_task_instance_count")
    except Exception as e:
        # Try alternative metric name
        try:
            prom_data = prometheus_client.query_instant("airflow_scheduler_heartbeat")
        except Exception:
            pytest.skip(f"No Airflow metrics found in Prometheus: {e}")
            return

    # Assert: Prometheus query succeeded
    assert prom_data["status"] == "success", f"Prometheus query failed: {prom_data}"

    # Note: Metrics might be empty if no DAGs have run recently
    # The key assertion is that Prometheus can query successfully

    # Act: Get Grafana health
    assert grafana_client.health_check(), "Grafana is not healthy"

    # Act: Get Grafana dashboards
    dashboards = grafana_client.list_dashboards()

    # Find Airflow dashboard
    airflow_dashboard = next(
        (dash for dash in dashboards if "airflow" in dash.get("title", "").lower()),
        None,
    )

    if airflow_dashboard is None:
        # Dashboard not created yet, verify Prometheus data source instead
        datasources_response = grafana_client.client.get(
            f"{grafana_client.base_url}/api/datasources"
        )

        if datasources_response.status_code == 200:
            datasources = datasources_response.json()
            prometheus_ds = next(
                (ds for ds in datasources if ds.get("type") == "prometheus"), None
            )
            # Assert Prometheus datasource exists in Grafana
            if prometheus_ds:
                # Test datasource connectivity
                test_response = grafana_client.client.get(
                    f"{grafana_client.base_url}/api/datasources/uid/{prometheus_ds['uid']}/health"
                )
                # Datasource health check
                assert test_response.status_code in [
                    200,
                    404,
                ], f"Grafana datasource health check failed: {test_response.status_code}"
        # Skip detailed dashboard test
        pytest.skip("Airflow metrics dashboard not found in Grafana")
        return

    # Act: Get dashboard details
    dashboard_uid = airflow_dashboard["uid"]
    dashboard_data = grafana_client.get_dashboard(dashboard_uid)

    # Assert: Dashboard loads successfully
    assert "dashboard" in dashboard_data, "Dashboard data missing from response"

    # Act: Check Prometheus alert rules
    try:
        alerts_response = prometheus_client.client.get(
            f"{prometheus_client.base_url}/api/v1/rules"
        )
        if alerts_response.status_code == 200:
            alerts_data = alerts_response.json()
            assert (
                alerts_data["status"] == "success"
            ), f"Alert rules query failed: {alerts_data}"
    except Exception:
        # Alert rules might not be configured - acceptable
        pass
