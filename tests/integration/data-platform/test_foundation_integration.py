"""Integration tests for Phase 1 foundation stack."""

import json
import subprocess


def run_command(cmd, check=True):
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise Exception(f"Command failed: {cmd}\nstderr: {result.stderr}")
    return result.stdout


class TestServiceHealth:
    """Verify all data platform services are running and healthy."""

    def test_all_services_running(self):
        """All data platform containers should be in running state."""
        output = run_command("docker compose ps --format json")
        lines = [line for line in output.strip().split("\n") if line]

        services_found = set()
        for line in lines:
            container = json.loads(line)
            name = container.get("Name", "")
            state = container.get("State", "")

            if "rideshare-minio" in name:
                services_found.add("minio")
                assert state == "running", f"MinIO not running: {state}"
            elif "rideshare-spark-master" in name:
                services_found.add("spark-master")
                assert state == "running", f"Spark master not running: {state}"
            elif "rideshare-spark-worker" in name:
                services_found.add("spark-worker")
                assert state == "running", f"Spark worker not running: {state}"
            elif "rideshare-spark-thrift-server" in name:
                services_found.add("spark-thrift-server")
                assert state == "running", f"Thrift server not running: {state}"
            elif "rideshare-localstack" in name:
                services_found.add("localstack")
                assert state == "running", f"LocalStack not running: {state}"

        expected = {
            "minio",
            "spark-master",
            "spark-worker",
            "spark-thrift-server",
            "localstack",
        }
        missing = expected - services_found
        assert not missing, f"Missing services: {missing}"

    def test_memory_limits_enforced(self):
        """Verify services respect memory limits (no OOMKilled)."""
        ps_output = run_command("docker compose ps")
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

    def test_spark_delta_write_read(self):
        """PySpark should write and read Delta tables via s3a://."""
        # Use existing test script mounted at /opt/spark-scripts
        output = run_command(
            "docker exec rideshare-spark-worker /opt/spark/bin/spark-submit "
            "/opt/spark-scripts/test-delta-access.py 2>&1"
        )
        assert "SUCCESS" in output, f"Delta write/read failed: {output[-500:]}"


class TestThriftServer:
    """Verify Spark Thrift Server accepts JDBC connections."""

    def test_thrift_server_connection(self):
        """Beeline should connect to Thrift Server."""
        cmd = (
            "docker exec rideshare-spark-thrift-server "
            '/opt/spark/bin/beeline -u jdbc:hive2://localhost:10000 -e "SHOW DATABASES;" 2>&1'
        )
        output = run_command(cmd)
        assert "default" in output.lower(), f"Cannot list databases: {output[-500:]}"

    def test_thrift_server_delta_query(self):
        """SQL query should read Delta table created by Spark test script."""
        # Query the table created by test-delta-access.py
        cmd = (
            "docker exec rideshare-spark-thrift-server "
            "/opt/spark/bin/beeline -u jdbc:hive2://localhost:10000 "
            '-e "SELECT * FROM delta.\\`s3a://rideshare-bronze/test-delta-table\\`;" 2>&1'
        )
        output = run_command(cmd)
        # test-delta-access.py inserts test1, test2, test3
        assert (
            "test1" in output or "test2" in output
        ), f"Cannot query Delta table: {output[-500:]}"


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
