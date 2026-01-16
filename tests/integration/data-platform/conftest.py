"""Pytest fixtures for foundation integration tests."""

import pytest
import boto3


@pytest.fixture(scope="session")
def minio_client():
    """S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
    )


@pytest.fixture(scope="session")
def localstack_secrets_client():
    """Secrets Manager client configured for LocalStack."""
    return boto3.client(
        "secretsmanager",
        endpoint_url="http://localhost:4566",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
