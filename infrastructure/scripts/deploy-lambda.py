#!/usr/bin/env python3
"""Deploy Lambda functions to LocalStack.

Deploys both auth-deploy and ai-chat Lambda functions.
Idempotent: creates on first run, updates function code on subsequent runs.

Usage:
    AWS_ENDPOINT_URL=http://localhost:4566 \
    AWS_ACCESS_KEY_ID=test \
    AWS_SECRET_ACCESS_KEY=test \
    AWS_DEFAULT_REGION=us-east-1 \
    python3 deploy-lambda.py

Environment:
    AWS_ENDPOINT_URL    - LocalStack endpoint (required)
    AWS_DEFAULT_REGION  - AWS region (default: us-east-1)
"""

from __future__ import annotations

import dataclasses
import io
import logging
import os
import sys
import zipfile
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_lambda import LambdaClient
    from mypy_boto3_lambda.type_defs import EnvironmentTypeDef
    from mypy_boto3_s3 import S3Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ROLE = "arn:aws:iam::000000000000:role/lambda-role"
RUNTIME: str = "python3.13"
HANDLER = "handler.lambda_handler"


@dataclasses.dataclass
class FunctionConfig:
    name: str
    handler_path: str
    source_dir: str | None = None
    extra_files: dict[str, str] = dataclasses.field(default_factory=dict)
    environment: dict[str, str] = dataclasses.field(default_factory=dict)


FUNCTIONS: list[FunctionConfig] = [
    FunctionConfig(
        name="auth-deploy",
        handler_path="/app/lambda/handler.py",
    ),
    FunctionConfig(
        name="ai-chat",
        handler_path="/app/lambda-ai-chat/handler.py",
        source_dir="/app/lambda-ai-chat",
        extra_files={
            "/app/ai-chat-docs/AI-CHAT-CONTEXT.md": "docs/AI-CHAT-CONTEXT.md",
        },
        environment={
            "LLM_PROVIDER": os.environ.get("LLM_PROVIDER", "mock"),
            "DAILY_BUDGET_USD": "5.00",
            "AI_CHAT_BUCKET": "rideshare-ai-chat",
        },
    ),
]

AI_CHAT_BUCKET = "rideshare-ai-chat"


def create_clients() -> tuple[LambdaClient, S3Client]:
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    if endpoint_url:
        logger.info("Using endpoint: %s (region: %s)", endpoint_url, region)
    else:
        logger.warning("AWS_ENDPOINT_URL not set — targeting real AWS")

    lambda_client: LambdaClient = boto3.client(
        "lambda",
        region_name=region,
        endpoint_url=endpoint_url,
    )
    s3_client: S3Client = boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint_url,
    )
    return lambda_client, s3_client


def create_zip(
    handler_path: str,
    source_dir: str | None = None,
    extra_files: dict[str, str] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if source_dir is None:
            zf.write(handler_path, "handler.py")
        else:
            for root, _dirs, files in os.walk(source_dir):
                # Skip venv, __pycache__, tests, and hidden directories
                rel_root = os.path.relpath(root, source_dir)
                if any(
                    part in ("venv", "__pycache__", ".git", ".pytest_cache")
                    for part in rel_root.split(os.sep)
                ):
                    continue
                for f in files:
                    if not f.endswith((".py", ".md")):
                        continue
                    if f.startswith("conftest") or f.startswith("test_"):
                        continue
                    full_path = os.path.join(root, f)
                    arc_name = os.path.relpath(full_path, source_dir)
                    zf.write(full_path, arc_name)
        for src_path, arc_name in (extra_files or {}).items():
            if os.path.exists(src_path):
                zf.write(src_path, arc_name)
            else:
                logger.warning("Extra file not found: %s", src_path)
    return buffer.getvalue()


def ensure_s3_bucket(s3_client: S3Client, bucket_name: str) -> None:
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        logger.info("[CREATED] S3 bucket: %s", bucket_name)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("BucketAlreadyExists", "BucketAlreadyOwnedByYou"):
            logger.info("[EXISTS] S3 bucket: %s", bucket_name)
        else:
            raise


def deploy_function(
    lambda_client: LambdaClient,
    config: FunctionConfig,
    zip_bytes: bytes,
) -> None:
    environment: EnvironmentTypeDef | None = (
        {"Variables": config.environment} if config.environment else None
    )

    try:
        if environment:
            lambda_client.create_function(
                FunctionName=config.name,
                Runtime=RUNTIME,
                Role=ROLE,
                Handler=HANDLER,
                Code={"ZipFile": zip_bytes},
                Environment=environment,
            )
        else:
            lambda_client.create_function(
                FunctionName=config.name,
                Runtime=RUNTIME,
                Role=ROLE,
                Handler=HANDLER,
                Code={"ZipFile": zip_bytes},
            )
        logger.info("[CREATED] %s", config.name)
    except ClientError as e:
        if e.response["Error"]["Code"] in (
            "ResourceConflictException",
            "ResourceInUseException",
        ):
            lambda_client.update_function_code(
                FunctionName=config.name,
                ZipFile=zip_bytes,
            )
            logger.info("[UPDATED] %s", config.name)
        else:
            raise


def main() -> int:
    logger.info("=" * 60)
    logger.info("Lambda Deploy Script")
    logger.info("=" * 60)

    lambda_client, s3_client = create_clients()

    # Create S3 buckets needed by Lambda functions
    ensure_s3_bucket(s3_client, AI_CHAT_BUCKET)

    # Deploy each function
    for config in FUNCTIONS:
        if not os.path.exists(config.handler_path):
            logger.error(
                "Handler not found at %s — skipping %s",
                config.handler_path,
                config.name,
            )
            continue
        zip_bytes = create_zip(config.handler_path, config.source_dir, config.extra_files)
        deploy_function(lambda_client, config, zip_bytes)

    logger.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
