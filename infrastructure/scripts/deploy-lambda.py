#!/usr/bin/env python3
"""Deploy auth-deploy Lambda function to LocalStack.

Packages handler.py into a zip and creates (or updates) the Lambda function.
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

import io
import logging
import os
import sys
import zipfile

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

FUNCTION_NAME = "auth-deploy"
HANDLER = "handler.lambda_handler"
RUNTIME = "python3.12"
# LocalStack accepts any syntactically valid ARN for the execution role.
ROLE = "arn:aws:iam::000000000000:role/lambda-role"
HANDLER_PATH = "/app/lambda/handler.py"


def create_lambda_client() -> boto3.client:
    """Create a boto3 Lambda client pointed at LocalStack."""
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    if endpoint_url:
        logger.info("Using endpoint: %s (region: %s)", endpoint_url, region)
    else:
        logger.warning("AWS_ENDPOINT_URL not set — targeting real AWS Lambda")

    return boto3.client(
        "lambda",
        region_name=region,
        endpoint_url=endpoint_url,
    )


def create_zip(handler_path: str) -> bytes:
    """Package handler.py into an in-memory zip."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(handler_path, "handler.py")
    return buffer.getvalue()


def deploy(client: boto3.client, zip_bytes: bytes) -> None:
    """Create or update the Lambda function."""
    try:
        client.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime=RUNTIME,
            Role=ROLE,
            Handler=HANDLER,
            Code={"ZipFile": zip_bytes},
        )
        logger.info("[CREATED] %s", FUNCTION_NAME)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("ResourceConflictException", "ResourceInUseException"):
            client.update_function_code(
                FunctionName=FUNCTION_NAME,
                ZipFile=zip_bytes,
            )
            logger.info("[UPDATED] %s", FUNCTION_NAME)
        else:
            raise


def main() -> int:
    """Package and deploy the Lambda function.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    logger.info("=" * 60)
    logger.info("Lambda Deploy Script")
    logger.info("=" * 60)

    if not os.path.exists(HANDLER_PATH):
        logger.error("Handler not found at %s", HANDLER_PATH)
        return 1

    try:
        client = create_lambda_client()
        zip_bytes = create_zip(HANDLER_PATH)
        deploy(client, zip_bytes)
        logger.info("Done.")
        return 0
    except Exception:
        logger.exception("Deployment failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
