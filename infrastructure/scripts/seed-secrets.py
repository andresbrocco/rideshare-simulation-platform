#!/usr/bin/env python3
"""Seed LocalStack Secrets Manager with consolidated credential groups.

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

    Overrides can also be placed in infrastructure/scripts/.env.secrets (one
    VAR=VALUE per line).  The file is gitignored and loaded automatically.

Exit codes:
    0 - All secrets seeded successfully
    1 - One or more secrets failed to seed
"""

import base64
import json
import logging
import os
import pathlib
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
# Non-Airflow passwords default to "admin". Keys are pre-disambiguated at
# source to avoid collisions when multiple services share the same env file.
SECRETS: dict[str, dict[str, str]] = {
    "rideshare/api-key": {
        "API_KEY": "admin",
    },
    "rideshare/core": {
        "KAFKA_SASL_USERNAME": "admin",
        "KAFKA_SASL_PASSWORD": "admin",
        "REDIS_PASSWORD": "admin",
        "SCHEMA_REGISTRY_USER": "admin",
        "SCHEMA_REGISTRY_PASSWORD": "admin",
        "GRAFANA_ADMIN_USER": "admin",
        "GRAFANA_ADMIN_PASSWORD": "admin",
    },
    "rideshare/data-pipeline": {
        "MINIO_ROOT_USER": "admin",
        "MINIO_ROOT_PASSWORD": "adminadmin",
        "POSTGRES_AIRFLOW_USER": "admin",
        "POSTGRES_AIRFLOW_PASSWORD": "admin",
        "POSTGRES_METASTORE_USER": "admin",
        "POSTGRES_METASTORE_PASSWORD": "admin",
        "FERNET_KEY": AIRFLOW_FERNET_KEY,
        "INTERNAL_API_SECRET_KEY": AIRFLOW_INTERNAL_API_SECRET_KEY,
        "JWT_SECRET": AIRFLOW_JWT_SECRET,
        "API_SECRET_KEY": AIRFLOW_API_SECRET_KEY,
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "admin",
    },
    "rideshare/admin-user": {
        "EMAIL": "admin@rideshare.local",
        "PASSWORD": "admin",
    },
    "rideshare/github-pat": {
        "GITHUB_PAT": "ghp_localstack_placeholder_token_DO_NOT_USE_IN_PRODUCTION",
    },
    "rideshare/llm-api-keys": {
        "anthropic": "",
        "openai": "",
        "google": "",
        "deepseek": "",
    },
}


def load_env_secrets() -> None:
    """Load overrides from .env.secrets file if it exists.

    The file is expected next to this script at infrastructure/scripts/.env.secrets.
    Each line should be VAR=VALUE (blank lines and #-comments are skipped).
    Values are loaded into os.environ so apply_overrides() picks them up.
    """
    env_file = pathlib.Path(__file__).parent / ".env.secrets"
    if not env_file.exists():
        return

    count = 0
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key and value:
            os.environ[key] = value
            count += 1

    logger.info("Loaded %d overrides from %s", count, env_file.name)


def apply_overrides(secrets: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Apply environment variable overrides to secret values.

    For each key in each secret group, checks for an OVERRIDE_<KEY> environment
    variable. If found, replaces the default value.

    Example: OVERRIDE_MINIO_ROOT_USER=myminio overrides the MINIO_ROOT_USER
    field in rideshare/data-pipeline.
    """
    for secret_name, fields in secrets.items():
        for key in fields:
            override_var = f"OVERRIDE_{key}"
            override_value = os.environ.get(override_var)
            # Also check uppercase variant so OVERRIDE_ANTHROPIC works for
            # lowercase field names like "anthropic".
            if override_value is None:
                override_var_upper = f"OVERRIDE_{key.upper()}"
                if override_var_upper != override_var:
                    override_value = os.environ.get(override_var_upper)
                    if override_value is not None:
                        override_var = override_var_upper
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

    load_env_secrets()
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
