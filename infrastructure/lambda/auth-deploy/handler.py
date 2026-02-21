import json
import os
import urllib.request
import urllib.error
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Constants
GITHUB_API_BASE = "https://api.github.com"
GITHUB_REPO = "andresbrocco/rideshare-simulation-platform"
GITHUB_WORKFLOW = "deploy.yml"
GITHUB_API_VERSION = "2022-11-28"
REQUEST_TIMEOUT = 10  # seconds

# Secret keys
SECRET_API_KEY = "rideshare/api-key"
SECRET_GITHUB_PAT = "rideshare/github-pat"

# CORS configuration
ALLOWED_ORIGINS = [
    "https://ridesharing.portfolio.andresbrocco.com",
    "http://localhost:5173",
]


def get_secrets_client() -> boto3.client:
    """Get Secrets Manager client configured for LocalStack or AWS."""
    config = Config(
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        signature_version="v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )

    endpoint_url = None
    if os.environ.get("LOCALSTACK_HOSTNAME"):
        endpoint_url = f"http://{os.environ['LOCALSTACK_HOSTNAME']}:4566"

    return boto3.client("secretsmanager", config=config, endpoint_url=endpoint_url)


def get_secret(secret_id: str) -> str:
    """Retrieve secret from AWS Secrets Manager.

    Args:
        secret_id: Secret identifier

    Returns:
        Secret string value

    Raises:
        ClientError: If secret cannot be retrieved
    """
    client = get_secrets_client()

    try:
        response = client.get_secret_value(SecretId=secret_id)

        if "SecretString" in response:
            secret_value = response["SecretString"]
            try:
                parsed = json.loads(secret_value)
                # Handle both formats: {"API_KEY": "..."} or plain string
                if isinstance(parsed, dict):
                    if "API_KEY" in parsed:
                        return parsed["API_KEY"]
                    if "GITHUB_PAT" in parsed:
                        return parsed["GITHUB_PAT"]
                return secret_value
            except json.JSONDecodeError:
                return secret_value

        raise ValueError(f"Secret {secret_id} is not a string secret")

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        print(f"Error retrieving secret {secret_id}: {error_code}")
        raise


def validate_api_key(provided_key: str) -> bool:
    """Validate provided API key against stored secret.

    Args:
        provided_key: API key from request

    Returns:
        True if valid, False otherwise
    """
    try:
        stored_key = get_secret(SECRET_API_KEY)
        return provided_key == stored_key
    except Exception as e:
        print(f"Error validating API key: {e}")
        return False


def github_api_request(
    method: str, path: str, github_pat: str, body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    """Make authenticated request to GitHub API.

    Args:
        method: HTTP method (GET, POST)
        path: API path (e.g., "/repos/owner/repo/actions/workflows/...")
        github_pat: GitHub Personal Access Token
        body: Request body for POST requests

    Returns:
        Tuple of (status_code, response_data)
    """
    url = f"{GITHUB_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {github_pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "rideshare-lambda-auth-deploy",
    }

    data = None
    if body:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            response_body = response.read().decode("utf-8")
            return response.status, json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_data = json.loads(error_body)
        except json.JSONDecodeError:
            error_data = {"message": error_body}
        return e.code, error_data
    except urllib.error.URLError as e:
        print(f"URL error calling GitHub API: {e}")
        return 502, {"message": "Failed to connect to GitHub API", "error": str(e)}
    except Exception as e:
        print(f"Unexpected error calling GitHub API: {e}")
        return 500, {"message": "Internal error calling GitHub API", "error": str(e)}


def handle_validate(api_key: str) -> tuple[int, dict[str, Any]]:
    """Handle validate action."""
    is_valid = validate_api_key(api_key)

    if is_valid:
        return 200, {"valid": True}
    return 401, {"valid": False, "error": "Invalid password"}


def handle_deploy(api_key: str) -> tuple[int, dict[str, Any]]:
    """Handle deploy action."""
    if not validate_api_key(api_key):
        return 401, {"error": "Invalid password"}

    try:
        github_pat = get_secret(SECRET_GITHUB_PAT)
    except Exception as e:
        print(f"Error retrieving GitHub PAT: {e}")
        return 500, {"error": "Failed to retrieve GitHub credentials"}

    path = f"/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/dispatches"
    body = {"ref": "main", "inputs": {"action": "deploy-all"}}

    status_code, response_data = github_api_request("POST", path, github_pat, body)

    # GitHub returns 204 No Content on successful workflow dispatch
    if status_code == 204:
        return 200, {
            "triggered": True,
            "workflow": GITHUB_WORKFLOW,
            "ref": "main",
        }

    print(f"GitHub API error: {status_code} - {response_data}")
    return 502, {
        "error": "Failed to trigger deployment",
        "details": response_data.get("message", "Unknown error"),
        "status_code": status_code,
    }


def handle_status(api_key: str) -> tuple[int, dict[str, Any]]:
    """Handle status action."""
    if not validate_api_key(api_key):
        return 401, {"error": "Invalid password"}

    try:
        github_pat = get_secret(SECRET_GITHUB_PAT)
    except Exception as e:
        print(f"Error retrieving GitHub PAT: {e}")
        return 500, {"error": "Failed to retrieve GitHub credentials"}

    path = f"/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/runs?per_page=1"

    status_code, response_data = github_api_request("GET", path, github_pat)

    if status_code == 200:
        workflow_runs = response_data.get("workflow_runs", [])

        if not workflow_runs:
            return 200, {"status": "idle"}

        latest_run = workflow_runs[0]
        return 200, {
            "status": latest_run.get("status", "unknown"),
            "conclusion": latest_run.get("conclusion"),
            "run_id": latest_run.get("id"),
            "created_at": latest_run.get("created_at"),
            "html_url": latest_run.get("html_url"),
        }

    print(f"GitHub API error: {status_code} - {response_data}")
    return 502, {
        "error": "Failed to query deployment status",
        "details": response_data.get("message", "Unknown error"),
        "status_code": status_code,
    }


def get_cors_headers(origin: str) -> dict[str, str]:
    """Get CORS headers for response.

    Args:
        origin: Origin header from request

    Returns:
        Dict of CORS headers
    """
    allowed_origin = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]

    return {
        "Access-Control-Allow-Origin": allowed_origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Requested-With",
        "Access-Control-Max-Age": "86400",
        "Content-Type": "application/json",
    }


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Lambda function handler for auth and deploy actions.

    Supports two invocation formats:
    - Function URL: event contains HTTP metadata and body as a JSON string.
      Returns a full HTTP response dict (statusCode, headers, body).
    - Direct invocation: event contains action/api_key directly (used by
      LocalStack /invocations endpoint in local dev).
      Returns the business response dict directly.

    Args:
        event: Lambda event from Function URL or direct invocation
        context: Lambda context

    Returns:
        Response dict (format depends on invocation type)
    """
    print(f"Received event: {json.dumps(event)}")

    # Direct invocation: action/api_key are top-level fields in the event.
    # The raw /invocations endpoint passes the request payload directly as the
    # event, so there is no HTTP wrapper. Return the business response directly.
    if "action" in event or "api_key" in event:
        action = event.get("action")
        api_key = event.get("api_key")

        if not action:
            return {"error": "Missing required field: action"}
        if not api_key:
            return {"error": "Missing required field: api_key"}

        handlers: dict[str, Any] = {
            "validate": handle_validate,
            "deploy": handle_deploy,
            "status": handle_status,
        }
        handler = handlers.get(action)
        if handler is None:
            return {
                "error": f"Unknown action: {action}",
                "valid_actions": ["validate", "deploy", "status"],
            }

        _, response_body = handler(api_key)
        return response_body

    # Function URL invocation: event is a full HTTP request envelope.
    # Extract origin for CORS
    headers_lower = {k.lower(): v for k, v in event.get("headers", {}).items()}
    origin = headers_lower.get("origin", ALLOWED_ORIGINS[0])
    cors_headers = get_cors_headers(origin)

    # Handle preflight OPTIONS request
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": "",
        }

    # Parse request body
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": cors_headers,
            "body": json.dumps({"error": "Invalid JSON in request body"}),
        }

    # Extract action and api_key
    action = body.get("action")
    api_key = body.get("api_key")

    # Validate required fields
    if not action:
        return {
            "statusCode": 400,
            "headers": cors_headers,
            "body": json.dumps({"error": "Missing required field: action"}),
        }

    if not api_key:
        return {
            "statusCode": 400,
            "headers": cors_headers,
            "body": json.dumps({"error": "Missing required field: api_key"}),
        }

    # Route to appropriate handler
    url_handlers: dict[str, Any] = {
        "validate": handle_validate,
        "deploy": handle_deploy,
        "status": handle_status,
    }

    url_handler = url_handlers.get(action)
    if url_handler is None:
        status_code = 400
        response_body = {
            "error": f"Unknown action: {action}",
            "valid_actions": ["validate", "deploy", "status"],
        }
    else:
        status_code, response_body = url_handler(api_key)

    return {
        "statusCode": status_code,
        "headers": cors_headers,
        "body": json.dumps(response_body),
    }
