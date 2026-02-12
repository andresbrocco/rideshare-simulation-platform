#!/usr/bin/env python3
"""Seed LocalStack Secrets Manager with all project credential groups.

Populates rideshare/* secrets in AWS Secrets Manager (LocalStack or real AWS).
Each secret group is a JSON object with credential key-value pairs. The script
is idempotent: it creates new secrets or updates existing ones.

Usage:
    AWS_ENDPOINT_URL=http://localhost:4566 \
    AWS_ACCESS_KEY_ID=test \
    AWS_SECRET_ACCESS_KEY=test \
    AWS_DEFAULT_REGION=us-east-1 \
    python3 seed-secrets.py

Environment:
    AWS_ENDPOINT_URL    - If set, connects to LocalStack; otherwise uses real AWS
    AWS_DEFAULT_REGION  - AWS region (default: us-east-1)
    OVERRIDE_<KEY>      - Override any individual secret value
                          (e.g., OVERRIDE_MINIO_ROOT_USER=myminioadmin)

Exit codes:
    0 - All secrets seeded successfully
    1 - One or more secrets failed to seed
"""

import base64
import json
import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_secretsmanager import SecretsManagerClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Deterministic Airflow cryptographic keys for local development.
# These are NOT production-secure; use properly rotated keys in production.
AIRFLOW_FERNET_KEY = base64.urlsafe_b64encode(
    b"admin-dev-fernet-key-00000000".ljust(32)[:32]
).decode()
AIRFLOW_INTERNAL_API_SECRET_KEY = base64.b64encode(b"admin-dev-internal-api-secret").decode()
AIRFLOW_JWT_SECRET = base64.b64encode(b"admin-dev-jwt-secret-key-00000").decode()
AIRFLOW_API_SECRET_KEY = base64.b64encode(b"admin-dev-api-secret-key-00000").decode()

# All project credential groups in rideshare/* namespace.
# Non-Airflow passwords default to "admin".
SECRETS: dict[str, dict[str, str]] = {
    "rideshare/api-key": {
        "API_KEY": "admin",
    },
    "rideshare/minio": {
        "MINIO_ROOT_USER": "admin",
        "MINIO_ROOT_PASSWORD": "admin",
    },
    "rideshare/redis": {
        "REDIS_PASSWORD": "admin",
    },
    "rideshare/kafka": {
        "KAFKA_SASL_USERNAME": "admin",
        "KAFKA_SASL_PASSWORD": "admin",
    },
    "rideshare/schema-registry": {
        "SCHEMA_REGISTRY_USER": "admin",
        "SCHEMA_REGISTRY_PASSWORD": "admin",
    },
    "rideshare/postgres-airflow": {
        "POSTGRES_USER": "admin",
        "POSTGRES_PASSWORD": "admin",
    },
    "rideshare/postgres-metastore": {
        "POSTGRES_USER": "admin",
        "POSTGRES_PASSWORD": "admin",
    },
    "rideshare/airflow": {
        "FERNET_KEY": AIRFLOW_FERNET_KEY,
        "INTERNAL_API_SECRET_KEY": AIRFLOW_INTERNAL_API_SECRET_KEY,
        "JWT_SECRET": AIRFLOW_JWT_SECRET,
        "API_SECRET_KEY": AIRFLOW_API_SECRET_KEY,
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "admin",
    },
    "rideshare/grafana": {
        "ADMIN_USER": "admin",
        "ADMIN_PASSWORD": "admin",
    },
    "rideshare/hive-thrift": {
        "LDAP_USERNAME": "admin",
        "LDAP_PASSWORD": "admin",
    },
    "rideshare/ldap": {
        "LDAP_ADMIN_PASSWORD": "admin",
        "LDAP_CONFIG_PASSWORD": "admin",
    },
}


def apply_overrides(secrets: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Apply environment variable overrides to secret values.

    For each key in each secret group, checks for an OVERRIDE_<KEY> environment
    variable. If found, replaces the default value.

    Example: OVERRIDE_MINIO_ROOT_USER=myminio overrides the MINIO_ROOT_USER
    field in rideshare/minio.
    """
    for secret_name, fields in secrets.items():
        for key in fields:
            override_var = f"OVERRIDE_{key}"
            override_value = os.environ.get(override_var)
            if override_value is not None:
                logger.info(
                    "  Override applied: %s in %s (from %s)",
                    key,
                    secret_name,
                    override_var,
                )
                fields[key] = override_value
    return secrets


def create_secretsmanager_client() -> SecretsManagerClient:
    """Create a boto3 Secrets Manager client.

    Uses AWS_ENDPOINT_URL for LocalStack connectivity when set.
    Falls back to standard AWS credential chain otherwise.
    """
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    if endpoint_url:
        logger.info("Using endpoint: %s (region: %s)", endpoint_url, region)
        return boto3.client("secretsmanager", region_name=region, endpoint_url=endpoint_url)

    logger.info("Using default AWS endpoint (region: %s)", region)
    return boto3.client("secretsmanager", region_name=region)


def upsert_secret(
    client: SecretsManagerClient, secret_name: str, secret_value: dict[str, str]
) -> bool:
    """Create or update a secret in Secrets Manager.

    Tries create_secret first. If the secret already exists
    (ResourceExistsException), falls back to update_secret.

    Returns True on success, False on failure.
    """
    secret_string = json.dumps(secret_value)

    try:
        client.create_secret(Name=secret_name, SecretString=secret_string)
        logger.info("  [CREATED] %s (%d keys)", secret_name, len(secret_value))
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceExistsException":
            try:
                client.update_secret(SecretId=secret_name, SecretString=secret_string)
                logger.info("  [UPDATED] %s (%d keys)", secret_name, len(secret_value))
                return True
            except ClientError as update_err:
                logger.error("  [FAILED] %s: update failed: %s", secret_name, update_err)
                return False
        else:
            logger.error("  [FAILED] %s: %s", secret_name, e)
            return False


def main() -> int:
    """Seed all project secrets into Secrets Manager.

    Returns:
        Exit code: 0 if all secrets seeded, 1 if any failed.
    """
    logger.info("=" * 60)
    logger.info("Secrets Seed Script")
    logger.info("=" * 60)

    secrets = apply_overrides(SECRETS)
    client = create_secretsmanager_client()

    logger.info("Seeding %d secret groups...", len(secrets))
    logger.info("-" * 60)

    succeeded = 0
    failed = 0

    for secret_name, secret_value in secrets.items():
        if upsert_secret(client, secret_name, secret_value):
            succeeded += 1
        else:
            failed += 1

    logger.info("-" * 60)
    logger.info("Results: %d succeeded, %d failed", succeeded, failed)

    if failed > 0:
        logger.error("Some secrets failed to seed. Check errors above.")
        return 1

    logger.info("All %d secret groups seeded successfully.", succeeded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
