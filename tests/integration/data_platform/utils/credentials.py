"""Credential loading utility for integration tests.

Fetches 4 consolidated rideshare/* secrets from LocalStack Secrets Manager
and maps them to environment variable names using the same key transforms as
infrastructure/scripts/fetch-secrets.py (the source of truth).

Usage:
    from tests.integration.data_platform.utils.credentials import fetch_all_credentials

    creds = fetch_all_credentials()
    # Returns {"MINIO_ROOT_USER": "admin", "KAFKA_SASL_USERNAME": "admin", ...}
"""

import json
import logging
import time

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

logger = logging.getLogger(__name__)

# LocalStack standard connection parameters (not real credentials).
_LOCALSTACK_ENDPOINT = "http://localhost:4566"
_LOCALSTACK_ACCESS_KEY = "test"
_LOCALSTACK_SECRET_KEY = "test"
_LOCALSTACK_REGION = "us-east-1"

# All rideshare/* secret names that the project seeds via seed-secrets.py.
_ALL_SECRET_NAMES = [
    "rideshare/api-key",
    "rideshare/core",
    "rideshare/data-pipeline",
    "rideshare/monitoring",
]

# Key transforms copied from infrastructure/scripts/fetch-secrets.py.
# That file is the source of truth; keep these in sync.
_AIRFLOW_KEY_MAPPING: dict[str, str] = {
    "FERNET_KEY": "AIRFLOW__CORE__FERNET_KEY",
    "INTERNAL_API_SECRET_KEY": "AIRFLOW__CORE__INTERNAL_API_SECRET_KEY",
    "JWT_SECRET": "AIRFLOW__API_AUTH__JWT_SECRET",
    "API_SECRET_KEY": "AIRFLOW__API__SECRET_KEY",
    "ADMIN_USERNAME": "AIRFLOW_ADMIN_USERNAME",
    "ADMIN_PASSWORD": "AIRFLOW_ADMIN_PASSWORD",
}

_GRAFANA_KEY_MAPPING: dict[str, str] = {
    "ADMIN_USER": "GF_SECURITY_ADMIN_USER",
    "ADMIN_PASSWORD": "GF_SECURITY_ADMIN_PASSWORD",
}


def _transform_keys(secret_name: str, fields: dict[str, str]) -> dict[str, str]:
    """Apply the same key transforms as fetch-secrets.py."""
    if secret_name == "rideshare/data-pipeline":
        return {_AIRFLOW_KEY_MAPPING.get(key, key): value for key, value in fields.items()}

    if secret_name == "rideshare/monitoring":
        return {_GRAFANA_KEY_MAPPING.get(key, key): value for key, value in fields.items()}

    return fields


def fetch_all_credentials(
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> dict[str, str]:
    """Fetch all rideshare/* credentials from LocalStack Secrets Manager.

    Connects to LocalStack, fetches every rideshare/* secret, and applies
    the same key transforms that fetch-secrets.py uses so the returned dict
    maps directly to the env var names that services and tests expect.

    Args:
        max_retries: Number of connection attempts (LocalStack may still be initializing).
        retry_delay: Seconds between retries.

    Returns:
        Flat dict mapping env-var names to their values, e.g.
        {"MINIO_ROOT_USER": "admin", "KAFKA_SASL_USERNAME": "admin", ...}

    Raises:
        RuntimeError: If LocalStack is unreachable or any secret is missing.
    """
    client = boto3.client(
        "secretsmanager",
        endpoint_url=_LOCALSTACK_ENDPOINT,
        aws_access_key_id=_LOCALSTACK_ACCESS_KEY,
        aws_secret_access_key=_LOCALSTACK_SECRET_KEY,
        region_name=_LOCALSTACK_REGION,
    )

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return _fetch_and_transform(client)
        except (EndpointConnectionError, ConnectionError) as exc:
            last_error = exc
            if attempt < max_retries:
                logger.warning(
                    "LocalStack not reachable (attempt %d/%d), retrying in %.0fs...",
                    attempt,
                    max_retries,
                    retry_delay,
                )
                time.sleep(retry_delay)

    raise RuntimeError(
        f"Could not connect to LocalStack at {_LOCALSTACK_ENDPOINT} "
        f"after {max_retries} attempts: {last_error}"
    )


def _fetch_and_transform(client: boto3.client) -> dict[str, str]:
    """Fetch all secrets and return the transformed env-var dict."""
    all_env_vars: dict[str, str] = {}
    missing: list[str] = []

    for secret_name in _ALL_SECRET_NAMES:
        try:
            response = client.get_secret_value(SecretId=secret_name)
            fields: dict[str, str] = json.loads(response["SecretString"])
            transformed = _transform_keys(secret_name, fields)
            all_env_vars.update(transformed)
        except ClientError as exc:
            missing.append(f"{secret_name}: {exc}")
        except (json.JSONDecodeError, KeyError) as exc:
            missing.append(f"{secret_name}: invalid format: {exc}")

    if missing:
        raise RuntimeError("Failed to fetch secrets from LocalStack:\n  " + "\n  ".join(missing))

    return all_env_vars
