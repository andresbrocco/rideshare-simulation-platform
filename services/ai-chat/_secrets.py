"""AWS Secrets Manager helper for LLM API key retrieval.

Reads the rideshare/llm-api-keys secret (JSON with per-provider keys) once per
Lambda container lifetime.  The module-level cache means warm invocations
skip the Secrets Manager round-trip entirely.

LocalStack is supported via the LOCALSTACK_HOSTNAME environment variable.
"""

import json
import os

import boto3
from botocore.config import Config

_LLM_API_KEYS: dict[str, str] | None = None


def _load_keys() -> dict[str, str]:
    """Fetch LLM API keys from Secrets Manager, caching for the container lifetime."""
    global _LLM_API_KEYS
    if _LLM_API_KEYS is not None:
        return _LLM_API_KEYS

    region = os.environ.get("AWS_REGION", "us-east-1")
    config = Config(region_name=region)

    endpoint_url: str | None = None
    localstack_host = os.environ.get("LOCALSTACK_HOSTNAME")
    if localstack_host:
        endpoint_url = f"http://{localstack_host}:4566"

    client = boto3.client("secretsmanager", config=config, endpoint_url=endpoint_url)
    secret = client.get_secret_value(SecretId="rideshare/llm-api-keys")
    _LLM_API_KEYS = json.loads(secret["SecretString"])
    return _LLM_API_KEYS


def get_llm_api_key(provider: str) -> str:
    """Return the API key for the given LLM provider.

    Args:
        provider: Provider name (e.g. "anthropic", "openai", "google", "deepseek").

    Returns:
        The API key string for that provider.

    Raises:
        KeyError: If the provider has no key in the secret.
    """
    keys = _load_keys()
    return keys[provider]


def get_available_providers() -> list[str]:
    """Return provider names that have a usable (non-empty, non-placeholder) API key.

    Returns:
        Sorted list of provider name strings.
    """
    keys = _load_keys()
    return sorted(name for name, key in keys.items() if key and not key.startswith("placeholder"))
