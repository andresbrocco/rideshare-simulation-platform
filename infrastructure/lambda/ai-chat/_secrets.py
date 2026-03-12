"""AWS Secrets Manager helper for LLM API key retrieval.

Reads the rideshare/llm-api-key secret (JSON, key: LLM_API_KEY) once per
Lambda container lifetime.  The module-level cache means warm invocations
skip the Secrets Manager round-trip entirely.

LocalStack is supported via the LOCALSTACK_HOSTNAME environment variable.
"""

import json
import os

import boto3
from botocore.config import Config

_LLM_API_KEY: str | None = None


def get_llm_api_key() -> str:
    """Return the LLM API key, fetching from Secrets Manager on first call.

    Subsequent calls within the same Lambda container return the cached value
    without making any network request.

    Returns:
        The API key string stored under the ``LLM_API_KEY`` JSON field in the
        ``rideshare/llm-api-key`` secret.
    """
    global _LLM_API_KEY
    if _LLM_API_KEY is not None:
        return _LLM_API_KEY

    region = os.environ.get("AWS_REGION", "us-east-1")
    config = Config(region_name=region)

    endpoint_url: str | None = None
    localstack_host = os.environ.get("LOCALSTACK_HOSTNAME")
    if localstack_host:
        endpoint_url = f"http://{localstack_host}:4566"

    client = boto3.client("secretsmanager", config=config, endpoint_url=endpoint_url)
    secret = client.get_secret_value(SecretId="rideshare/llm-api-key")
    _LLM_API_KEY = json.loads(secret["SecretString"])["LLM_API_KEY"]
    return _LLM_API_KEY
