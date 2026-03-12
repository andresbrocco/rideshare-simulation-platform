"""Analytics logging for the ai-chat Lambda.

Every conversation turn is written as a single-line JSON record (JSONL) to a
unique S3 key under ``analytics/{year}/{month}/{uuid}.jsonl``.

Using a unique key per turn avoids read-modify-write races when Lambda scales
to multiple concurrent instances — each invocation writes to its own object.
When querying, scan the monthly prefix and filter by session_id:

    SELECT * FROM analytics_table
    WHERE session_id = 'abc'
    ORDER BY turn_number

All S3 errors are caught and logged to CloudWatch via print().  The function
never raises so a failed analytics write never blocks the LLM response.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.config import Config


def _get_s3_client() -> Any:
    """Return a boto3 S3 client, pointing at LocalStack when running locally.

    Returns:
        A boto3 S3 client instance.
    """
    config = Config(
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        retries={"max_attempts": 2, "mode": "standard"},
    )
    endpoint_url = None
    localstack_host = os.environ.get("LOCALSTACK_HOSTNAME")
    if localstack_host:
        endpoint_url = f"http://{localstack_host}:4566"
    return boto3.client("s3", config=config, endpoint_url=endpoint_url)


def log_turn(
    bucket: str,
    session_id: str,
    turn_number: int,
    user_message: str,
    assistant_message: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    from_cache: bool,
    has_visitor_email: bool = False,
) -> None:
    """Write a single conversation turn as a JSONL record to S3.

    The record is written to a unique key so that concurrent Lambda invocations
    never contend on the same object.  The key format is::

        analytics/{year}/{month}/{uuid}.jsonl

    All exceptions are caught and reported via print() so a transient S3 error
    never surfaces to the visitor.

    Args:
        bucket: Name of the S3 bucket used for analytics storage.
        session_id: UUID string identifying the session.
        turn_number: 1-based turn index within the session.
        user_message: The visitor's question for this turn.
        assistant_message: The assistant's response for this turn.
        input_tokens: Input tokens consumed (0 for cached responses).
        output_tokens: Output tokens generated (0 for cached responses).
        cost_usd: Estimated cost in USD (0.0 for cached responses).
        from_cache: True when the response came from the starter cache.
        has_visitor_email: True when the session has a visitor email on file.
    """
    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        year = timestamp[:4]
        month = timestamp[5:7]

        model = "cache" if from_cache else os.environ.get("LLM_MODEL", "unknown")

        record: dict[str, Any] = {
            "timestamp": timestamp,
            "session_id": session_id,
            "turn_number": turn_number,
            "question": user_message,
            "response": assistant_message,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "model": model,
            "cached": from_cache,
            "has_visitor_email": has_visitor_email,
        }

        key = f"analytics/{year}/{month}/{uuid.uuid4()}.jsonl"
        _get_s3_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(record) + "\n",
            ContentType="application/x-ndjson",
        )
    except Exception as exc:
        print(f"Analytics write failed (non-fatal): {exc}")
