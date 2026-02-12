#!/usr/bin/env python3
"""Fetch secrets from Secrets Manager and write grouped env files.

Reads all rideshare/* secrets from AWS Secrets Manager (LocalStack or real AWS)
and writes grouped environment files for Docker Compose profiles:
  /secrets/core.env          - Simulation runtime services
  /secrets/data-pipeline.env - ETL, ingestion, orchestration
  /secrets/monitoring.env    - Observability stack

Usage:
    AWS_ENDPOINT_URL=http://localhost:4566 \
    AWS_ACCESS_KEY_ID=test \
    AWS_SECRET_ACCESS_KEY=test \
    AWS_DEFAULT_REGION=us-east-1 \
    python3 fetch-secrets.py

Environment:
    AWS_ENDPOINT_URL    - If set, connects to LocalStack; otherwise uses real AWS
    AWS_DEFAULT_REGION  - AWS region (default: us-east-1)
    SECRETS_OUTPUT_DIR  - Output directory for env files (default: /secrets)

Exit codes:
    0 - All env files written successfully
    1 - One or more operations failed
"""

import json
import logging
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_secretsmanager import SecretsManagerClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Profile-to-secrets mapping: which secrets belong to each env file.
PROFILE_SECRETS: dict[str, list[str]] = {
    "core.env": [
        "rideshare/api-key",
        "rideshare/redis",
        "rideshare/kafka",
        "rideshare/schema-registry",
    ],
    "data-pipeline.env": [
        "rideshare/minio",
        "rideshare/postgres-airflow",
        "rideshare/postgres-metastore",
        "rideshare/airflow",
        "rideshare/hive-thrift",
        "rideshare/ldap",
    ],
    "monitoring.env": [
        "rideshare/grafana",
    ],
}

# Airflow secret keys get flattened to double-underscore env var format.
# Non-config keys (ADMIN_*) get a simple AIRFLOW_ prefix.
AIRFLOW_KEY_MAPPING: dict[str, str] = {
    "FERNET_KEY": "AIRFLOW__CORE__FERNET_KEY",
    "INTERNAL_API_SECRET_KEY": "AIRFLOW__CORE__INTERNAL_API_SECRET_KEY",
    "JWT_SECRET": "AIRFLOW__API__JWT_SECRET",
    "API_SECRET_KEY": "AIRFLOW__API__SECRET_KEY",
    "ADMIN_USERNAME": "AIRFLOW_ADMIN_USERNAME",
    "ADMIN_PASSWORD": "AIRFLOW_ADMIN_PASSWORD",
}

# Explicit key mappings for secrets with generic key names that would collide
# when multiple secrets share the same env file. Keys not listed here pass through.
SECRET_KEY_TRANSFORMS: dict[str, dict[str, str]] = {
    "rideshare/postgres-airflow": {
        "POSTGRES_USER": "POSTGRES_AIRFLOW_USER",
        "POSTGRES_PASSWORD": "POSTGRES_AIRFLOW_PASSWORD",
    },
    "rideshare/postgres-metastore": {
        "POSTGRES_USER": "POSTGRES_METASTORE_USER",
        "POSTGRES_PASSWORD": "POSTGRES_METASTORE_PASSWORD",
    },
    "rideshare/grafana": {
        "ADMIN_USER": "GF_SECURITY_ADMIN_USER",
        "ADMIN_PASSWORD": "GF_SECURITY_ADMIN_PASSWORD",
    },
    "rideshare/hive-thrift": {
        "LDAP_USERNAME": "HIVE_LDAP_USERNAME",
        "LDAP_PASSWORD": "HIVE_LDAP_PASSWORD",
    },
}


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


def fetch_secret(client: SecretsManagerClient, secret_name: str) -> dict[str, str] | None:
    """Fetch a single secret and parse its JSON value.

    Returns the parsed key-value dict, or None on failure.
    """
    try:
        response = client.get_secret_value(SecretId=secret_name)
        parsed: dict[str, str] = json.loads(response["SecretString"])
        return parsed
    except ClientError as e:
        logger.error("  [FAILED] %s: %s", secret_name, e)
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("  [FAILED] %s: invalid secret format: %s", secret_name, e)
        return None


def transform_keys(secret_name: str, fields: dict[str, str]) -> dict[str, str]:
    """Transform secret field keys to env var names.

    Airflow secrets get flattened to double-underscore format.
    Postgres, Grafana, and Hive secrets get disambiguated to avoid collisions.
    All other secrets keep their original key names.
    """
    if secret_name == "rideshare/airflow":
        return {AIRFLOW_KEY_MAPPING.get(key, key): value for key, value in fields.items()}

    key_map = SECRET_KEY_TRANSFORMS.get(secret_name)
    if key_map:
        return {key_map.get(key, key): value for key, value in fields.items()}

    return fields


def format_env_line(key: str, value: str) -> str:
    """Format a single KEY=value line for an env file.

    Quotes values containing spaces; leaves others unquoted.
    """
    if " " in value:
        return f'{key}="{value}"'
    return f"{key}={value}"


def write_env_file(path: Path, env_vars: dict[str, str]) -> bool:
    """Write key-value pairs to an env file.

    Format: KEY=value (one per line), sorted alphabetically.
    Returns True on success, False on failure.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [format_env_line(key, value) for key, value in sorted(env_vars.items())]
        path.write_text("\n".join(lines) + "\n")
        logger.info("  [WRITTEN] %s (%d variables)", path, len(env_vars))
        return True
    except OSError as e:
        logger.error("  [FAILED] %s: %s", path, e)
        return False


def main() -> int:
    """Fetch secrets and write grouped env files.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    logger.info("=" * 60)
    logger.info("Secrets Fetch Script")
    logger.info("=" * 60)

    output_dir = Path(os.environ.get("SECRETS_OUTPUT_DIR", "/secrets"))
    client = create_secretsmanager_client()

    # Collect all unique secret names across profiles.
    all_secret_names = sorted({name for names in PROFILE_SECRETS.values() for name in names})
    logger.info("Fetching %d secrets...", len(all_secret_names))
    logger.info("-" * 60)

    fetched: dict[str, dict[str, str]] = {}
    failed_count = 0

    for secret_name in all_secret_names:
        fields = fetch_secret(client, secret_name)
        if fields is not None:
            fetched[secret_name] = fields
            logger.info("  [FETCHED] %s (%d keys)", secret_name, len(fields))
        else:
            failed_count += 1

    if failed_count > 0:
        logger.error(
            "%d secrets failed to fetch. Cannot write complete env files.",
            failed_count,
        )
        return 1

    # Write grouped env files.
    logger.info("-" * 60)
    logger.info("Writing env files to %s...", output_dir)

    write_failed = 0

    for profile_name, secret_names in PROFILE_SECRETS.items():
        env_vars: dict[str, str] = {}
        for secret_name in secret_names:
            transformed = transform_keys(secret_name, fetched[secret_name])
            env_vars.update(transformed)

        if not write_env_file(output_dir / profile_name, env_vars):
            write_failed += 1

    logger.info("-" * 60)

    if write_failed > 0:
        logger.error("Failed to write %d env files.", write_failed)
        return 1

    logger.info("All %d env files written successfully.", len(PROFILE_SECRETS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
