"""S3-backed starter question response cache for the ai-chat Lambda.

Loaded once on Lambda cold start via ``load_cache``, then consulted on every
subsequent invocation via ``get_cached_response``.  Cache misses are non-fatal
and fall through to live LLM calls.

The cache JSON stored in S3 follows this schema::

    {
        "generated_at": "<ISO-8601 timestamp>",
        "docs_hash": "sha256:<hex>",
        "responses": {
            "<question text>": "<response text>",
            ...
        }
    }

The S3 key is always ``cache/starter-responses.json``.

Usage::

    from starter_cache import load_cache, get_cached_response

    load_cache(bucket="my-bucket")          # call once on cold start
    text = get_cached_response("What is the architecture of this platform?")
    if text is not None:
        # serve from cache
        ...
"""

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# S3 key where the generated cache file lives
# ---------------------------------------------------------------------------

_CACHE_S3_KEY = "cache/starter-responses.json"

# ---------------------------------------------------------------------------
# Module-level cache variable — populated once on first cold-start call to
# load_cache() and reused for all warm invocations.
# ---------------------------------------------------------------------------

_CACHE: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_s3_client() -> Any:
    """Return a boto3 S3 client.

    Isolated into its own function so tests can patch it cleanly without
    affecting other modules that also create S3 clients.

    Returns:
        A boto3 S3 client instance.
    """
    return boto3.client("s3")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_cache(bucket: str) -> dict[str, Any] | None:
    """Load the starter-response cache from S3 into the module-level variable.

    Idempotent: if ``_CACHE`` is already populated (warm Lambda invocation)
    the function returns immediately without making any S3 calls.

    The function swallows all errors so that a missing or corrupt cache file
    never prevents the Lambda from serving requests via live LLM calls.

    Args:
        bucket: Name of the S3 bucket containing the cache file.

    Returns:
        The parsed cache dict on success, or ``None`` if the file is missing
        or any error occurs.
    """
    global _CACHE

    # Warm invocation — reuse the already-loaded data without hitting S3.
    if _CACHE is not None:
        return _CACHE

    try:
        client = _get_s3_client()
        response = client.get_object(Bucket=bucket, Key=_CACHE_S3_KEY)
        raw_bytes: bytes = response["Body"].read()
        data: dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))
        _CACHE = data
        logger.info("Starter cache loaded from s3://%s/%s", bucket, _CACHE_S3_KEY)
        return _CACHE

    except ClientError as exc:
        error_code: str = exc.response["Error"]["Code"]
        if error_code in ("NoSuchKey", "404"):
            logger.info(
                "Starter cache not found at s3://%s/%s — falling back to live LLM",
                bucket,
                _CACHE_S3_KEY,
            )
        else:
            logger.warning(
                "Unexpected S3 error loading starter cache (code=%s) — " "falling back to live LLM",
                error_code,
            )
        return None

    except Exception:
        logger.warning(
            "Failed to load starter cache from s3://%s/%s — falling back to live LLM",
            bucket,
            _CACHE_S3_KEY,
            exc_info=True,
        )
        return None


def get_cached_response(message: str) -> str | None:
    """Return the cached response for an exact question match.

    Performs a case-sensitive, exact-string lookup against the ``responses``
    dict in ``_CACHE``.  Partial matches and case variations both return
    ``None`` so that callers always fall through to a live LLM call.

    Args:
        message: The user's message string to look up.

    Returns:
        The cached response text if an exact match exists, otherwise ``None``.
    """
    if _CACHE is None:
        return None

    responses: dict[str, str] = _CACHE.get("responses", {})
    return responses.get(message)
