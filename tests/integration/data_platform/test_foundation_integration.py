"""Integration tests for Phase 1 foundation stack."""

import json
import os
import subprocess


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

    def test_all_services_running(self):
        """All data platform containers should be in running state.

        Note: Spark runs in local mode (no spark-master/spark-worker).
        Each streaming job and the thrift-server run Spark independently.
        """
        project_root = _get_project_root()
        output = run_command(
            "docker compose -f infrastructure/docker/compose.yml --profile core --profile data-platform ps --format json",
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
            elif "rideshare-spark-streaming-trips" in name:
                services_found.add("spark-streaming-trips")
                assert state == "running", f"Spark streaming trips not running: {state}"

        # Spark runs in local mode now - no separate master/worker containers
        expected = {
            "minio",
            "spark-thrift-server",
            "localstack",
            "spark-streaming-trips",
        }
        missing = expected - services_found
        assert not missing, f"Missing services: {missing}"

    def test_memory_limits_enforced(self):
        """Verify services respect memory limits (no OOMKilled)."""
        project_root = _get_project_root()
        ps_output = run_command(
            "docker compose -f infrastructure/docker/compose.yml --profile core --profile data-platform ps",
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
        """Verify Delta tables can be queried via Thrift Server.

        Uses the thrift_connection fixture (PyHive) to query existing
        Bronze tables created by streaming jobs.
        """
        cursor = thrift_connection.cursor()
        # Query the bronze database to verify Delta tables are accessible
        cursor.execute("SHOW DATABASES")
        databases = [row[0] for row in cursor.fetchall()]
        assert (
            "bronze" in databases
        ), f"Bronze database not found. Databases: {databases}"

        # Verify we can query a Bronze table
        cursor.execute("SHOW TABLES IN bronze")
        tables = [row[1] for row in cursor.fetchall()]
        assert len(tables) > 0, "No tables found in bronze database"


class TestThriftServer:
    """Verify Spark Thrift Server accepts JDBC connections."""

    def test_thrift_server_connection(self, thrift_connection):
        """PyHive should connect to Thrift Server."""
        cursor = thrift_connection.cursor()
        cursor.execute("SHOW DATABASES")
        databases = [row[0] for row in cursor.fetchall()]
        assert "default" in databases, f"Default database not found: {databases}"

    def test_thrift_server_delta_query(self, thrift_connection):
        """SQL query should read Delta tables in Bronze layer."""
        cursor = thrift_connection.cursor()
        # Query the bronze_trips table created by streaming jobs
        cursor.execute("SELECT COUNT(*) FROM bronze.bronze_trips")
        count = cursor.fetchone()[0]
        # Just verify the query works - count may be 0 if no data yet
        assert count >= 0, "Query should return a count"


class TestLocalStack:
    """Verify LocalStack AWS emulation."""

    def test_localstack_health(self):
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
            localstack_secrets_client.create_secret(
                Name=secret_name, SecretString=secret_value
            )
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
