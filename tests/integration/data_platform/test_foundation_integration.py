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

        Note: Bronze ingestion uses a lightweight Python service with
        confluent-kafka consumer (no Spark Structured Streaming).
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
            elif "rideshare-localstack" in name:
                services_found.add("localstack")
                assert state == "running", f"LocalStack not running: {state}"
            elif "rideshare-bronze-ingestion" in name:
                services_found.add("bronze-ingestion")
                assert state == "running", f"Bronze ingestion not running: {state}"

        expected = {
            "minio",
            "localstack",
            "bronze-ingestion",
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
