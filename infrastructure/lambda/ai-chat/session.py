"""S3-backed session state management for the ai-chat Lambda.

Sessions are stored as JSON objects at `sessions/{uuid}.json` in the ai-chat
S3 bucket. Each session tracks the conversation history and turn counter.

Session schema::

    {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "visitor_email": "user@example.com",  # or null
        "messages": [
            {"role": "user", "content": "How does the simulation work?"},
            {"role": "assistant", "content": "The simulation uses SimPy..."}
        ],
        "turn_number": 1,
        "created_at": "2026-03-11T10:00:00+00:00"
    }

Failure semantics:
- ``create_session``: S3 write failure raises exception → caller returns 500.
- ``get_session``: ``NoSuchKey`` returns ``None`` → caller returns 404;
  other S3 errors propagate → caller returns 500.
- ``update_session``: Any S3 error raises → caller returns 500.

Sessions expire automatically via an S3 lifecycle rule (24h TTL) configured
on the bucket in Ticket 001.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

_S3_KEY_PREFIX = "sessions"


def _get_s3_client() -> Any:
    """Return a boto3 S3 client, pointing at LocalStack when running locally.

    The client is created fresh on each call; Lambda reuse caches the module
    so the environment variables are always evaluated at startup time. For
    local development, set ``LOCALSTACK_HOSTNAME`` to the LocalStack host.

    Returns:
        A boto3 S3 client instance.
    """
    config = Config(
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        retries={"max_attempts": 3, "mode": "standard"},
    )
    endpoint_url = None
    localstack_host = os.environ.get("LOCALSTACK_HOSTNAME")
    if localstack_host:
        endpoint_url = f"http://{localstack_host}:4566"
    return boto3.client("s3", config=config, endpoint_url=endpoint_url)


def create_session(bucket: str, visitor_email: str | None = None) -> str:
    """Create a new chat session and persist it to S3.

    Generates a random UUID, writes an empty session document to
    ``sessions/{uuid}.json``, and returns the UUID string.

    Args:
        bucket: Name of the S3 bucket used for session storage.
        visitor_email: Optional email address of the visitor, stored in the
            session for analytics purposes.

    Returns:
        The new session's UUID string.

    Raises:
        botocore.exceptions.ClientError: If the S3 write fails.
    """
    session_id = str(uuid.uuid4())
    session_data: dict[str, Any] = {
        "session_id": session_id,
        "visitor_email": visitor_email,
        "messages": [],
        "turn_number": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _get_s3_client().put_object(
        Bucket=bucket,
        Key=f"{_S3_KEY_PREFIX}/{session_id}.json",
        Body=json.dumps(session_data),
        ContentType="application/json",
    )
    return session_id


def get_session(bucket: str, session_id: str) -> dict[str, Any] | None:
    """Read a session from S3 and return it as a dict.

    Args:
        bucket: Name of the S3 bucket used for session storage.
        session_id: UUID string identifying the session.

    Returns:
        Parsed session dict if the key exists, or ``None`` if the session
        is not found (``NoSuchKey`` / ``404``).

    Raises:
        botocore.exceptions.ClientError: For any S3 error other than a
            missing key, e.g. access-denied or internal S3 errors.
    """
    try:
        response = _get_s3_client().get_object(
            Bucket=bucket,
            Key=f"{_S3_KEY_PREFIX}/{session_id}.json",
        )
        body: bytes = response["Body"].read()
        parsed: dict[str, Any] = json.loads(body)
        return parsed
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("NoSuchKey", "404"):
            return None
        raise


def update_session(
    bucket: str,
    session_id: str,
    user_message: str,
    assistant_message: str,
    turn_number: int,
) -> None:
    """Append a conversation turn to the session and persist it to S3.

    Reads the current session, appends the user and assistant messages to
    the conversation history, updates the turn counter, and writes the
    result back to ``sessions/{session_id}.json``.

    Args:
        bucket: Name of the S3 bucket used for session storage.
        session_id: UUID string identifying the session.
        user_message: The visitor's message for this turn.
        assistant_message: The assistant's response for this turn.
        turn_number: The new turn number after this exchange.

    Raises:
        botocore.exceptions.ClientError: If the S3 read or write fails.
    """
    session_data = get_session(bucket, session_id)
    if session_data is None:
        session_data = {
            "session_id": session_id,
            "visitor_email": None,
            "messages": [],
            "turn_number": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    session_data["messages"].append({"role": "user", "content": user_message})
    session_data["messages"].append({"role": "assistant", "content": assistant_message})
    session_data["turn_number"] = turn_number

    _get_s3_client().put_object(
        Bucket=bucket,
        Key=f"{_S3_KEY_PREFIX}/{session_id}.json",
        Body=json.dumps(session_data),
        ContentType="application/json",
    )
