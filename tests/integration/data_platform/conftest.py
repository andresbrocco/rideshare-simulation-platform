"""Pytest fixtures for data platform integration tests.

This module provides fixtures for:
- Docker container lifecycle management (Ticket 012)
- Service client connections (Ticket 013)
- Table cleanup and event generation (Ticket 014)
- Service verification (Ticket 015)
"""

import json
import os
import subprocess
import time
from typing import Dict, Any, List

import boto3
import httpx
import pytest
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from pyhive import hive

from tests.integration.data_platform.utils.api_clients import (
    AirflowClient,
    GrafanaClient,
    PrometheusClient,
    SupersetClient,
)
from tests.integration.data_platform.utils.sql_helpers import (
    clean_bronze_tables as cleanup_bronze,
    clean_gold_tables as cleanup_gold,
    clean_silver_tables as cleanup_silver,
    count_rows,
)
from tests.integration.data_platform.utils.wait_helpers import (
    poll_until_records_present,
    wait_for_condition,
)
from tests.integration.data_platform.fixtures.driver_events import (
    generate_driver_profile_events,
    generate_driver_status_events,
)
from tests.integration.data_platform.fixtures.gps_events import generate_gps_pings
from tests.integration.data_platform.fixtures.rider_events import (
    generate_rider_profile_events,
)
from tests.integration.data_platform.fixtures.trip_events import generate_trip_lifecycle


# =============================================================================
# Session-scoped Docker lifecycle fixtures (Ticket 012)
# =============================================================================


@pytest.fixture(scope="session")
def docker_compose():
    """Manage Docker Compose container lifecycle.

    Starts core and data-platform profiles at session start,
    stops all containers at session end.
    """
    compose_file = "infrastructure/docker/compose.yml"
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )

    # Start containers
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            compose_file,
            "--profile",
            "core",
            "--profile",
            "data-platform",
            "up",
            "-d",
        ],
        check=True,
        cwd=project_root,
    )

    yield

    # Teardown: stop containers
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            compose_file,
            "--profile",
            "core",
            "--profile",
            "data-platform",
            "down",
        ],
        check=False,  # Don't fail if containers already stopped
        cwd=project_root,
    )


@pytest.fixture(scope="session")
def wait_for_services(docker_compose):
    """Wait for all services to be healthy.

    Depends on docker_compose fixture. Polls health endpoints
    with exponential backoff until all services report healthy.
    """

    def check_minio_healthy():
        try:
            response = httpx.get("http://localhost:9000/minio/health/live", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    def check_kafka_healthy():
        try:
            # Check Schema Registry as proxy for Kafka readiness
            response = httpx.get("http://localhost:8085/subjects", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    def check_thrift_server_healthy():
        try:
            response = httpx.get(
                "http://localhost:4041/json/", timeout=5.0, follow_redirects=True
            )
            return response.status_code == 200
        except Exception:
            return False

    def check_airflow_healthy():
        try:
            response = httpx.get(
                "http://localhost:8082/api/v1/monitor/health",
                auth=("admin", "admin"),
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    # Wait for each service
    wait_for_condition(
        condition=check_minio_healthy,
        timeout_seconds=120,
        poll_interval=2.0,
        description="MinIO health endpoint",
    )

    wait_for_condition(
        condition=check_kafka_healthy,
        timeout_seconds=120,
        poll_interval=2.0,
        description="Kafka/Schema Registry health",
    )

    wait_for_condition(
        condition=check_thrift_server_healthy,
        timeout_seconds=180,
        poll_interval=5.0,
        description="Spark Thrift Server health",
    )

    # Only wait for Airflow if the container is running
    airflow_container_check = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "name=rideshare-airflow-webserver",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        text=True,
    )
    if "rideshare-airflow-webserver" in airflow_container_check.stdout:
        wait_for_condition(
            condition=check_airflow_healthy,
            timeout_seconds=180,
            poll_interval=5.0,
            description="Airflow webserver health",
        )

    yield


# =============================================================================
# Session-scoped service client fixtures (Ticket 013)
# =============================================================================


@pytest.fixture(scope="session")
def minio_client(wait_for_services):
    """S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
    )


@pytest.fixture(scope="session")
def localstack_secrets_client(wait_for_services):
    """Secrets Manager client configured for LocalStack."""
    return boto3.client(
        "secretsmanager",
        endpoint_url="http://localhost:4566",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )


@pytest.fixture(scope="session")
def kafka_admin(wait_for_services):
    """Kafka AdminClient for topic management.

    Creates test topics on setup.
    """
    admin = AdminClient({"bootstrap.servers": "localhost:9092"})

    # Create test topics (will ignore if already exist)
    topics = [
        NewTopic("trips", num_partitions=4, replication_factor=1),
        NewTopic("gps-pings", num_partitions=8, replication_factor=1),
        NewTopic("driver-status", num_partitions=4, replication_factor=1),
        NewTopic("driver-profiles", num_partitions=2, replication_factor=1),
        NewTopic("rider-profiles", num_partitions=2, replication_factor=1),
        NewTopic("surge-updates", num_partitions=4, replication_factor=1),
        NewTopic("ratings", num_partitions=4, replication_factor=1),
        NewTopic("payments", num_partitions=4, replication_factor=1),
    ]

    fs = admin.create_topics(topics)
    # Wait for topic creation (ignore errors if topics exist)
    for topic, f in fs.items():
        try:
            f.result()
        except Exception:
            pass  # Topic may already exist

    yield admin


@pytest.fixture(scope="session")
def kafka_producer(wait_for_services):
    """Kafka Producer with JSON serializer configured."""
    producer = Producer(
        {
            "bootstrap.servers": "localhost:9092",
            "client.id": "integration-test-producer",
        }
    )

    yield producer

    # Flush any pending messages on teardown
    producer.flush()


@pytest.fixture(scope="session")
def thrift_connection(wait_for_services):
    """PyHive connection to Spark Thrift Server.

    Connection pool for SQL queries against Delta tables.
    """
    connection = hive.Connection(
        host="localhost", port=10000, database="default", auth="NOSASL"
    )

    yield connection

    connection.close()


@pytest.fixture(scope="session")
def airflow_client(wait_for_services):
    """HTTP client for Airflow REST API with basic auth."""
    client = AirflowClient(
        base_url="http://localhost:8082", username="admin", password="admin"
    )

    yield client

    client.close()


@pytest.fixture(scope="session")
def superset_client(wait_for_services):
    """HTTP client for Superset REST API with session-based auth."""
    client = SupersetClient(
        base_url="http://localhost:8088", username="admin", password="admin"
    )

    yield client

    client.close()


@pytest.fixture(scope="session")
def prometheus_client(wait_for_services):
    """HTTP client for Prometheus API (no auth required)."""
    client = PrometheusClient(base_url="http://localhost:9090")

    yield client

    client.close()


@pytest.fixture(scope="session")
def grafana_client(wait_for_services):
    """HTTP client for Grafana API with basic auth."""
    client = GrafanaClient(
        base_url="http://localhost:3001", username="admin", password="admin"
    )

    yield client

    client.close()


# =============================================================================
# Function-scoped table cleanup fixtures (Ticket 014)
# =============================================================================


@pytest.fixture(scope="function")
def clean_bronze_tables(thrift_connection):
    """Truncate all Bronze layer tables while preserving schemas.

    Runs before each test to ensure clean state.
    """
    cleanup_bronze(thrift_connection)
    yield


@pytest.fixture(scope="function")
def clean_silver_tables(thrift_connection):
    """Truncate all Silver layer tables while preserving schemas.

    Runs before each test to ensure clean state.
    """
    cleanup_silver(thrift_connection)
    yield


@pytest.fixture(scope="function")
def clean_gold_tables(thrift_connection):
    """Truncate all Gold layer tables while preserving schemas.

    Runs before each test to ensure clean state.
    """
    cleanup_gold(thrift_connection)
    yield


# =============================================================================
# Function-scoped event generator fixtures (Ticket 014)
# =============================================================================


@pytest.fixture(scope="function")
def test_trip_events() -> List[Dict[str, Any]]:
    """Generate controlled trip lifecycle events for testing.

    Returns list of 6 events: requested, matched, driver_en_route,
    driver_arrived, started, completed.
    """
    return generate_trip_lifecycle(
        trip_id="test-trip-001",
        rider_id="test-rider-001",
        driver_id="test-driver-001",
        surge_multiplier=1.0,
        fare=15.00,
    )


@pytest.fixture(scope="function")
def test_gps_events() -> List[Dict[str, Any]]:
    """Generate controlled GPS ping events for testing.

    Returns list of 100 GPS pings for 5 different drivers.
    """
    events = []
    for driver_num in range(1, 6):
        driver_id = f"test-driver-{driver_num:03d}"
        pings = generate_gps_pings(
            driver_id=driver_id,
            num_pings=20,
            start_location=[-23.5505, -46.6333],
        )
        events.extend(pings)
    return events


@pytest.fixture(scope="function")
def test_driver_events() -> List[Dict[str, Any]]:
    """Generate controlled driver status and profile events.

    Returns list of driver status transitions.
    """
    return generate_driver_status_events(
        driver_id="test-driver-001",
        num_transitions=5,
    )


@pytest.fixture(scope="function")
def test_profile_events() -> Dict[str, List[Dict[str, Any]]]:
    """Generate driver and rider profile create/update events.

    Returns dict with 'driver_profiles' and 'rider_profiles' lists.
    """
    driver_profiles = generate_driver_profile_events(
        driver_ids=["test-driver-001", "test-driver-002"],
    )

    rider_profiles = generate_rider_profile_events(
        rider_ids=["test-rider-001", "test-rider-002"],
    )

    return {
        "driver_profiles": driver_profiles,
        "rider_profiles": rider_profiles,
    }


@pytest.fixture(scope="function")
def published_events(kafka_producer, test_trip_events) -> List[Dict[str, Any]]:
    """Publish test events to Kafka and wait for acks.

    Publishes test_trip_events to 'trips' topic.
    Returns after all acks received.
    """
    for event in test_trip_events:
        kafka_producer.produce(
            topic="trips",
            value=json.dumps(event).encode("utf-8"),
            key=event["trip_id"].encode("utf-8"),
        )

    # Wait for all messages to be delivered
    kafka_producer.flush(timeout=10.0)

    yield test_trip_events


@pytest.fixture(scope="function")
def wait_for_bronze_ingestion(thrift_connection, published_events):
    """Wait until published events appear in Bronze layer.

    Polls bronze.bronze_trips table with configurable timeout (default 60s).
    Raises TimeoutError if events don't appear in time.
    """
    expected_count = len(published_events)

    def query_bronze_count():
        return count_rows(thrift_connection, "bronze.bronze_trips")

    poll_until_records_present(
        query_callback=query_bronze_count,
        expected_count=expected_count,
        timeout_seconds=60,
        poll_interval=2.0,
        description="bronze.bronze_trips table",
    )

    yield


# =============================================================================
# Module-scoped service verification fixtures (Ticket 015)
# =============================================================================


@pytest.fixture(scope="module")
def streaming_jobs_running(docker_compose):
    """Verify all 8 Spark Structured Streaming jobs are running.

    Checks that spark-submit process exists in each streaming container.
    Module-scoped: runs once per test module.
    """
    streaming_containers = [
        "rideshare-spark-streaming-trips",
        "rideshare-spark-streaming-gps-pings",
        "rideshare-spark-streaming-driver-status",
        "rideshare-spark-streaming-surge-updates",
        "rideshare-spark-streaming-ratings",
        "rideshare-spark-streaming-payments",
        "rideshare-spark-streaming-driver-profiles",
        "rideshare-spark-streaming-rider-profiles",
    ]

    for container in streaming_containers:
        # Check if SparkSubmit process is running in container
        # (Spark runs as java with org.apache.spark.deploy.SparkSubmit class)
        result = subprocess.run(
            ["docker", "exec", container, "pgrep", "-f", "SparkSubmit"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Streaming job not running in {container}. "
                f"SparkSubmit process not found."
            )

    yield


@pytest.fixture(scope="module")
def bronze_tables_initialized(docker_compose):
    """Verify bronze-init container completed successfully.

    Waits for container to exit with code 0 (Bronze tables created).
    Module-scoped: runs once per test module.
    """
    container_name = "rideshare-bronze-init"
    max_wait_seconds = 180
    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        # Check container status
        result = subprocess.run(
            ["docker", "inspect", container_name, "--format", "{{.State.ExitCode}}"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            exit_code = result.stdout.strip()
            if exit_code == "0":
                # Container exited successfully
                yield
                return
            elif exit_code != "":
                # Container exited with non-zero code
                raise RuntimeError(
                    f"bronze-init container failed with exit code {exit_code}"
                )

        # Container still running or not found, wait and retry
        time.sleep(5)

    raise TimeoutError(
        f"bronze-init container did not complete within {max_wait_seconds} seconds"
    )


@pytest.fixture(scope="module")
def airflow_dags_loaded(wait_for_services, airflow_client):
    """Verify Airflow DAGs are loaded without import errors.

    Queries /api/v1/dags endpoint to check DAG parsing.
    Module-scoped: runs once per test module.
    """
    # List all DAGs
    dags = airflow_client.list_dags()

    if not isinstance(dags, list):
        raise RuntimeError("Airflow /api/v1/dags did not return a list")

    yield
