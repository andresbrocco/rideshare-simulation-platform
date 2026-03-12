"""CLI script: generate and upload the starter question response cache.

Run this script manually after deploying the Lambda to pre-generate cached
answers for the four starter questions shown in the frontend chat UI.

The script:
1. Reads ``docs/AI-CHAT-CONTEXT.md`` (adjacent to this script) and computes
   its SHA-256 hash.
2. Builds the system prompt used by the Lambda handler.
3. Calls the configured LLM provider for each of the four starter questions.
4. Writes the result to S3 as ``cache/starter-responses.json``.

Configuration is via environment variables so the same script works against
LocalStack (dev) and real AWS (production).

Environment variables::

    LLM_PROVIDER          Provider name: anthropic | openai | google | deepseek | mock
    LLM_MODEL             Model identifier (ignored by mock provider)
    AI_CHAT_BUCKET        S3 bucket name where the cache file will be written
    AWS_ENDPOINT_URL      Optional — override for LocalStack (e.g. http://localhost:4566)
    AWS_ACCESS_KEY_ID     AWS / LocalStack credentials
    AWS_SECRET_ACCESS_KEY AWS / LocalStack credentials
    AWS_DEFAULT_REGION    AWS region (default: us-east-1)

Example (LocalStack)::

    LLM_PROVIDER=mock \\
    AI_CHAT_BUCKET=rideshare-ai-chat \\
    AWS_ENDPOINT_URL=http://localhost:4566 \\
    AWS_ACCESS_KEY_ID=test \\
    AWS_SECRET_ACCESS_KEY=test \\
    AWS_DEFAULT_REGION=us-east-1 \\
    ./venv/bin/python3 generate_starter_cache.py
"""

import hashlib
import json
import logging
import os
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any

import boto3

from llm_adapter import get_provider

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOCS_FILENAME = "AI-CHAT-CONTEXT.md"
CACHE_S3_KEY = "cache/starter-responses.json"

STARTER_QUESTIONS: list[str] = [
    "What is the architecture of this platform?",
    "How does the simulation engine work?",
    "What technologies are used?",
    "How does data flow through the system?",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_docs() -> str:
    """Read the AI-CHAT-CONTEXT.md file adjacent to this script.

    Returns:
        File contents as a string.

    Raises:
        SystemExit: If the file does not exist.
    """
    docs_path = pathlib.Path(__file__).parent / "docs" / DOCS_FILENAME
    if not docs_path.exists():
        logger.error("Docs file not found: %s", docs_path)
        sys.exit(1)
    content = docs_path.read_text(encoding="utf-8")
    logger.info("Read docs from %s (%d bytes)", docs_path, len(content))
    return content


def _compute_hash(content: str) -> str:
    """Compute a SHA-256 hash of the given string.

    Args:
        content: Text to hash.

    Returns:
        Hash string in the form ``sha256:<hex>``.
    """
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _build_system_prompt(docs_content: str) -> str:
    """Wrap docs content in the same XML tags the Lambda handler uses.

    Args:
        docs_content: Raw markdown docs content.

    Returns:
        System prompt string ready for the LLM provider.
    """
    return f"<documentation>\n{docs_content}\n</documentation>"


def _generate_responses(system_prompt: str, provider_name: str, model: str) -> dict[str, str]:
    """Call the LLM provider once per starter question and collect responses.

    Args:
        system_prompt: System prompt to pass to the provider.
        provider_name: LLM provider name (e.g. ``"anthropic"``, ``"mock"``).
        model: Model identifier string (ignored by mock provider).

    Returns:
        Dict mapping each starter question to its generated response text.

    Raises:
        SystemExit: If any LLM call fails.
    """
    provider = get_provider(provider=provider_name, model=model)
    responses: dict[str, str] = {}

    for question in STARTER_QUESTIONS:
        logger.info("Generating response for: %s", question)
        try:
            llm_response = provider.complete(
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": question}],
            )
            responses[question] = llm_response.text
            logger.info(
                "  Done — %d input tokens, %d output tokens",
                llm_response.input_tokens,
                llm_response.output_tokens,
            )
        except Exception as exc:
            logger.error("LLM call failed for question %r: %s", question, exc)
            sys.exit(1)

    return responses


def _write_cache_to_s3(
    bucket: str,
    docs_hash: str,
    responses: dict[str, str],
) -> None:
    """Serialise the cache payload and upload it to S3.

    Args:
        bucket: Target S3 bucket name.
        docs_hash: SHA-256 hash of the docs file in ``sha256:<hex>`` format.
        responses: Dict mapping starter questions to their response texts.

    Raises:
        SystemExit: If the S3 upload fails.
    """
    payload: dict[str, Any] = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "docs_hash": docs_hash,
        "responses": responses,
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")

    endpoint_url: str | None = os.environ.get("AWS_ENDPOINT_URL")
    s3 = boto3.client("s3", endpoint_url=endpoint_url)

    try:
        s3.put_object(
            Bucket=bucket,
            Key=CACHE_S3_KEY,
            Body=body,
            ContentType="application/json",
        )
        logger.info("Cache written to s3://%s/%s (%d bytes)", bucket, CACHE_S3_KEY, len(body))
    except Exception as exc:
        logger.error("Failed to write cache to S3: %s", exc)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate and upload the starter question response cache."""
    provider_name = os.environ.get("LLM_PROVIDER", "mock")
    model = os.environ.get("LLM_MODEL", "")
    bucket = os.environ.get("AI_CHAT_BUCKET", "")

    if not bucket:
        logger.error(
            "AI_CHAT_BUCKET environment variable is required. "
            "Set it to the name of the S3 bucket."
        )
        sys.exit(1)

    logger.info("Starting starter cache generation")
    logger.info("  LLM provider : %s", provider_name)
    logger.info("  LLM model    : %s (empty = provider default)", model)
    logger.info("  S3 bucket    : %s", bucket)

    docs_content = _read_docs()
    docs_hash = _compute_hash(docs_content)
    logger.info("Docs hash: %s", docs_hash)

    system_prompt = _build_system_prompt(docs_content)
    responses = _generate_responses(
        system_prompt=system_prompt,
        provider_name=provider_name,
        model=model,
    )

    _write_cache_to_s3(bucket=bucket, docs_hash=docs_hash, responses=responses)
    logger.info("Done — %d starter responses cached", len(responses))


if __name__ == "__main__":
    main()
