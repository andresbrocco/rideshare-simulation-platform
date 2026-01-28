"""Integration tests for Phase 1 foundation stack."""

import json
import os
import subprocess

import pytest


# Module-level marker: requires core and data-pipeline profiles
pytestmark = pytest.mark.requires_profiles("core", "data-pipeline")


def _get_project_root() -> str:
    """Get the project root directory."""
    # tests/integration/data_platform/ -> tests/integration/ -> tests/ -> repo root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def run_command(cmd, check=True, cwd=None):
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if check and result.returncode != 0:
        raise Exception(f"Command failed: {cmd}\nstderr: {result.stderr}")
    return result.stdout


class TestServiceHealth:
    """Verify all data platform services are running and healthy."""

    def test_all_services_running(self, wait_for_services):
        """All data platform containers should be in running state.

        Note: Spark runs in local mode (no spark-master/spark-worker).
        Each streaming job and the thrift-server run Spark independently.
        """
        project_root = _get_project_root()
        output = run_command(
            "docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline ps --format json",
            cwd=project_root,
        )
        lines = [line for line in output.strip().split("\n") if line]

        services_found = set()
        for line in lines:
            container = json.loads(line)
            name = container.get("Name", "")
            state = container.get("State", "")

            if "rideshare-minio" in name:
                services_found.add("minio")
                assert state == "running", f"MinIO not running: {state}"
            elif "rideshare-spark-thrift-server" in name:
                services_found.add("spark-thrift-server")
                assert state == "running", f"Thrift server not running: {state}"
            elif "rideshare-localstack" in name:
                services_found.add("localstack")
                assert state == "running", f"LocalStack not running: {state}"
            elif "rideshare-bronze-ingestion-low-volume" in name:
                services_found.add("bronze-ingestion-low-volume")
                assert state == "running", f"Bronze ingestion low-volume not running: {state}"

        # Spark runs in local mode now - no separate master/worker containers
        # Note: As of streaming consolidation (2026-01-26), bronze-ingestion-low-volume
        # handles trips and 6 other topics (driver_status, surge_updates, etc.)
        expected = {
            "minio",
            "spark-thrift-server",
            "localstack",
            "bronze-ingestion-low-volume",
        }
        missing = expected - services_found
        assert not missing, f"Missing services: {missing}"

    def test_memory_limits_enforced(self, wait_for_services):
        """Verify services respect memory limits (no OOMKilled)."""
        project_root = _get_project_root()
        ps_output = run_command(
            "docker compose -f infrastructure/docker/compose.yml --profile core --profile data-pipeline ps",
            cwd=project_root,
        )
        assert "OOMKilled" not in ps_output, "Service was OOM killed"


class TestMinIO:
    """Verify MinIO S3 storage is properly configured."""

    def test_minio_buckets_exist(self, minio_client):
        """MinIO should have all four required buckets."""
        response = minio_client.list_buckets()
        bucket_names = [b["Name"] for b in response["Buckets"]]

        required = [
            "rideshare-bronze",
            "rideshare-silver",
            "rideshare-gold",
            "rideshare-checkpoints",
        ]
        for bucket in required:
            assert bucket in bucket_names, f"Missing bucket: {bucket}"

    def test_minio_bucket_accessible(self, minio_client):
        """Should be able to list objects in buckets."""
        for bucket in ["rideshare-bronze", "rideshare-silver", "rideshare-gold"]:
            response = minio_client.list_objects_v2(Bucket=bucket, MaxKeys=1)
            assert "Name" in response, f"Cannot access bucket: {bucket}"


class TestSparkDelta:
    """Verify Spark can read/write Delta tables to MinIO."""

    def test_spark_delta_write_read(self, thrift_connection):
        """Verify Delta tables can be created, written to, and read from.

        Creates a test Delta table to verify Spark's Delta Lake integration
        works correctly, without depending on streaming job data.
        """
        cursor = thrift_connection.cursor()

        test_db = "spark_delta_test_db"
        test_table = "delta_write_read_test"

        try:
            # Create test database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {test_db}")

            # Create a Delta table
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {test_db}.{test_table} (
                    trip_id STRING,
                    driver_id STRING,
                    rider_id STRING,
                    fare_amount DOUBLE
                ) USING DELTA
                """
            )

            # Write test data
            cursor.execute(
                f"""
                INSERT INTO {test_db}.{test_table} VALUES
                ('trip_001', 'driver_001', 'rider_001', 25.50),
                ('trip_002', 'driver_002', 'rider_002', 15.75)
                """
            )

            # Read and verify the data
            cursor.execute(
                f"SELECT trip_id, fare_amount FROM {test_db}.{test_table} ORDER BY trip_id"
            )
            rows = cursor.fetchall()
            assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
            assert rows[0][0] == "trip_001"
            assert rows[0][1] == 25.50
            assert rows[1][0] == "trip_002"
            assert rows[1][1] == 15.75

            # Verify Delta-specific feature: table history
            cursor.execute(f"DESCRIBE HISTORY {test_db}.{test_table}")
            history = cursor.fetchall()
            assert len(history) >= 1, "Delta table should have history"

        finally:
            # Cleanup
            cursor.execute(f"DROP TABLE IF EXISTS {test_db}.{test_table}")
            cursor.execute(f"DROP DATABASE IF EXISTS {test_db}")


class TestThriftServer:
    """Verify Spark Thrift Server accepts JDBC connections."""

    def test_thrift_server_connection(self, thrift_connection):
        """PyHive should connect to Thrift Server."""
        cursor = thrift_connection.cursor()
        cursor.execute("SHOW DATABASES")
        databases = [row[0] for row in cursor.fetchall()]
        assert "default" in databases, f"Default database not found: {databases}"

    def test_thrift_server_delta_query(self, thrift_connection):
        """SQL query should execute Delta table operations successfully.

        Creates a temporary Delta table to verify Thrift Server can handle
        Delta queries, without depending on data from streaming jobs.
        """
        cursor = thrift_connection.cursor()

        # Create a test database and Delta table to verify Delta query capability
        test_db = "thrift_test_db"
        test_table = "test_delta_table"

        try:
            # Create test database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {test_db}")

            # Create a Delta table with test data
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {test_db}.{test_table} (
                    id INT,
                    name STRING,
                    created_at TIMESTAMP
                ) USING DELTA
                """
            )

            # Insert test data
            cursor.execute(
                f"""
                INSERT INTO {test_db}.{test_table} VALUES
                (1, 'test_record_1', current_timestamp()),
                (2, 'test_record_2', current_timestamp())
                """
            )

            # Query the Delta table to verify it works
            cursor.execute(f"SELECT COUNT(*) FROM {test_db}.{test_table}")
            count = cursor.fetchone()[0]
            assert count == 2, f"Expected 2 records, got {count}"

            # Verify we can read specific columns (Delta-specific query)
            cursor.execute(f"SELECT id, name FROM {test_db}.{test_table} ORDER BY id")
            rows = cursor.fetchall()
            assert len(rows) == 2
            assert rows[0][0] == 1
            assert rows[0][1] == "test_record_1"

        finally:
            # Cleanup: drop test table and database
            cursor.execute(f"DROP TABLE IF EXISTS {test_db}.{test_table}")
            cursor.execute(f"DROP DATABASE IF EXISTS {test_db}")


class TestLocalStack:
    """Verify LocalStack AWS emulation."""

    def test_localstack_health(self, wait_for_services):
        """LocalStack health endpoint should respond."""
        output = run_command("curl -s http://localhost:4566/_localstack/health")
        health = json.loads(output)
        assert health.get("services", {}).get("secretsmanager") in [
            "available",
            "running",
        ]

    def test_localstack_secrets_manager(self, localstack_secrets_client):
        """Should create and retrieve secrets."""
        secret_name = "integration-test-secret"
        secret_value = "test-value-123"

        # Create or update secret
        try:
            localstack_secrets_client.create_secret(Name=secret_name, SecretString=secret_value)
        except localstack_secrets_client.exceptions.ResourceExistsException:
            localstack_secrets_client.put_secret_value(
                SecretId=secret_name, SecretString=secret_value
            )

        # Retrieve and verify
        response = localstack_secrets_client.get_secret_value(SecretId=secret_name)
        assert response["SecretString"] == secret_value


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
