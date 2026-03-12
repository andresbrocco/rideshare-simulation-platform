"""Daily budget cap enforcement for the ai-chat Lambda.

Tracks cumulative LLM spend per calendar day using a JSON counter stored in S3
at ``budget/{YYYY-MM-DD}-counter.json``.  The counter is read before each LLM
call and updated after a successful response.

Counter schema::

    {
        "date": "2026-03-11",
        "total_cost_usd": 3.421500,
        "total_requests": 42
    }

Race condition behaviour:
    When two Lambda instances execute concurrently they may both read the same
    counter value, pass the budget check, and each write an incremented copy
    (last-writer wins).  This means the final counter may undercount by one
    request and the daily limit can be exceeded by at most one LLM call.  At
    portfolio traffic volumes (mostly single-digit concurrent users) this is
    acceptable without resorting to DynamoDB atomic counters.

Counter keys expire automatically via the 7-day S3 lifecycle rule configured
on the bucket in Ticket 001.
"""

import json
import os
from datetime import date
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def _get_s3_client() -> Any:
    """Return a boto3 S3 client, pointing at LocalStack when running locally.

    Uses the ``LOCALSTACK_HOSTNAME`` environment variable to detect a local
    development environment and override the endpoint URL accordingly.

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


def _today_key() -> str:
    """Return the S3 key for today's budget counter.

    Returns:
        Key string of the form ``budget/YYYY-MM-DD-counter.json``.
    """
    return f"budget/{date.today().isoformat()}-counter.json"


def _read_counter(bucket: str) -> dict[str, Any] | None:
    """Read today's budget counter from S3.

    Args:
        bucket: Name of the S3 bucket used for budget storage.

    Returns:
        Parsed counter dict if the key exists, or ``None`` if there is no
        counter for today (``NoSuchKey`` / ``404``).

    Raises:
        botocore.exceptions.ClientError: For any S3 error other than a
            missing key, e.g. access-denied.
    """
    try:
        response = _get_s3_client().get_object(Bucket=bucket, Key=_today_key())
        body: bytes = response["Body"].read()
        parsed: dict[str, Any] = json.loads(body)
        return parsed
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("NoSuchKey", "404"):
            return None
        raise


def check_budget(bucket: str, daily_budget_usd: float) -> bool:
    """Return True when today's accumulated cost has reached the daily limit.

    A missing counter is treated as $0.00 spent, so this function returns
    ``False`` when no counter exists (the first call of the day).

    Args:
        bucket: Name of the S3 bucket used for budget storage.
        daily_budget_usd: Maximum allowed spend in USD for a single day.

    Returns:
        ``True`` when ``total_cost_usd >= daily_budget_usd``, ``False`` when
        under limit or when no counter exists yet.

    Raises:
        botocore.exceptions.ClientError: If the S3 read fails for any reason
            other than a missing key.
    """
    counter = _read_counter(bucket)
    if counter is None:
        return False
    return float(counter.get("total_cost_usd", 0.0)) >= daily_budget_usd


def update_budget(bucket: str, cost: float) -> None:
    """Increment today's budget counter by ``cost`` and write it back to S3.

    If no counter exists yet for today a new one is created.  The counter
    stores the running total cost (rounded to 6 decimal places) and a request
    count.

    Args:
        bucket: Name of the S3 bucket used for budget storage.
        cost: Cost of the LLM call in USD to add to today's total.

    Raises:
        botocore.exceptions.ClientError: If the S3 read or write fails.
    """
    counter = _read_counter(bucket)
    today = date.today().isoformat()

    if counter is None:
        counter = {"date": today, "total_cost_usd": 0.0, "total_requests": 0}

    counter["total_cost_usd"] = round(float(counter["total_cost_usd"]) + cost, 6)
    counter["total_requests"] = int(counter.get("total_requests", 0)) + 1
    counter["date"] = today

    _get_s3_client().put_object(
        Bucket=bucket,
        Key=_today_key(),
        Body=json.dumps(counter),
        ContentType="application/json",
    )
