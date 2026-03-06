import concurrent.futures
import json
import os
import time
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

# Session management constants
SSM_SESSION_PARAM = "/rideshare/session/deadline"
SCHEDULER_GROUP = "default"
SCHEDULER_NAME = "rideshare-auto-teardown"
GITHUB_TEARDOWN_WORKFLOW = "teardown.yml"
SESSION_STEP_MINUTES = 15
MAX_REMAINING_SECONDS = 2 * 3600  # 2 hours
PLATFORM_COST_PER_HOUR = 0.31
RESCHEDULE_DELAY_SECONDS = 300  # 5 min
TEARDOWN_TIMEOUT_SECONDS = 15 * 60  # 15 min — auto-clear stale tearing_down flag
DEPLOYING_TIMEOUT_SECONDS = 30 * 60  # 30 min — auto-clear stale deploying session

SERVICE_HEALTH_ENDPOINTS: dict[str, str] = {
    "simulation_api": "https://api.ridesharing.portfolio.andresbrocco.com/health",
    "grafana": "https://grafana.ridesharing.portfolio.andresbrocco.com/api/health",
    "airflow": "https://airflow.ridesharing.portfolio.andresbrocco.com/api/v2/monitor/health",
    "trino": "https://trino.ridesharing.portfolio.andresbrocco.com/v1/info",
    "prometheus": "https://prometheus.ridesharing.portfolio.andresbrocco.com/-/healthy",
}
HEALTH_CHECK_TIMEOUT = 5  # seconds

NO_AUTH_ACTIONS = {"session-status", "auto-teardown", "service-health", "teardown-status"}

TEARDOWN_STEP_RANGES = [
    (0, 5),  # UI step 0: Saving simulation checkpoint
    (5, 6),  # UI step 1: Cleaning up DNS
    (6, 7),  # UI step 2: Destroying infrastructure
    (7, 10),  # UI step 3: Verifying cleanup
    (10, 11),  # UI step 4: Finalizing
]

TEARDOWN_UI_LABELS = [
    "Saving simulation checkpoint...",
    "Cleaning up DNS records...",
    "Destroying infrastructure...",
    "Verifying cleanup...",
    "Finalizing...",
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


def get_ssm_client() -> boto3.client:
    """Get SSM client configured for LocalStack or AWS."""
    config = Config(
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        signature_version="v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )

    endpoint_url = None
    if os.environ.get("LOCALSTACK_HOSTNAME"):
        endpoint_url = f"http://{os.environ['LOCALSTACK_HOSTNAME']}:4566"

    return boto3.client("ssm", config=config, endpoint_url=endpoint_url)


def get_scheduler_client() -> boto3.client:
    """Get EventBridge Scheduler client configured for LocalStack or AWS."""
    config = Config(
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        signature_version="v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )

    endpoint_url = None
    if os.environ.get("LOCALSTACK_HOSTNAME"):
        endpoint_url = f"http://{os.environ['LOCALSTACK_HOSTNAME']}:4566"

    return boto3.client("scheduler", config=config, endpoint_url=endpoint_url)


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


def get_session() -> dict[str, Any] | None:
    """Read session state from SSM Parameter Store.

    Returns:
        Session dict with deployed_at/deadline, or None if no active session.
    """
    client = get_ssm_client()
    try:
        response = client.get_parameter(Name=SSM_SESSION_PARAM)
        return json.loads(response["Parameter"]["Value"])
    except ClientError as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            return None
        raise


def _upsert_schedule(deadline_ts: int) -> None:
    """Create or update the EventBridge one-time schedule for auto-teardown."""
    client = get_scheduler_client()
    role_arn = os.environ.get("SCHEDULER_ROLE_ARN", "")
    target_arn = os.environ.get("SELF_FUNCTION_ARN", "")

    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(deadline_ts, tz=timezone.utc)
    schedule_expression = f"at({dt.strftime('%Y-%m-%dT%H:%M:%S')})"

    schedule_kwargs: dict[str, Any] = {
        "Name": SCHEDULER_NAME,
        "GroupName": SCHEDULER_GROUP,
        "ScheduleExpression": schedule_expression,
        "ScheduleExpressionTimezone": "UTC",
        "FlexibleTimeWindow": {"Mode": "OFF"},
        "Target": {
            "Arn": target_arn,
            "RoleArn": role_arn,
            "Input": json.dumps({"action": "auto-teardown"}),
        },
        "ActionAfterCompletion": "DELETE",
    }

    try:
        client.update_schedule(**schedule_kwargs)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            client.create_schedule(**schedule_kwargs)
        else:
            raise


def create_session(deployed_at: int, deadline: int) -> None:
    """Create a new session in SSM and schedule auto-teardown."""
    client = get_ssm_client()
    session_data = json.dumps({"deployed_at": deployed_at, "deadline": deadline})
    client.put_parameter(
        Name=SSM_SESSION_PARAM,
        Value=session_data,
        Type="String",
        Overwrite=True,
    )
    _upsert_schedule(deadline)


def create_session_deploying(deployed_at: int) -> None:
    """Create a deploying session in SSM without scheduling teardown.

    Stores only deployed_at — no deadline. The countdown starts later
    when the frontend calls activate-session after health check passes.
    """
    client = get_ssm_client()
    session_data = json.dumps({"deployed_at": deployed_at})
    client.put_parameter(
        Name=SSM_SESSION_PARAM,
        Value=session_data,
        Type="String",
        Overwrite=True,
    )


def update_session_deadline(new_deadline: int) -> None:
    """Update session deadline in SSM and reschedule auto-teardown."""
    session = get_session()
    if session is None:
        raise ValueError("No active session")
    session["deadline"] = new_deadline
    client = get_ssm_client()
    client.put_parameter(
        Name=SSM_SESSION_PARAM,
        Value=json.dumps(session),
        Type="String",
        Overwrite=True,
    )
    _upsert_schedule(new_deadline)


def delete_session() -> None:
    """Delete session from SSM and remove the schedule."""
    client = get_ssm_client()
    try:
        client.delete_parameter(Name=SSM_SESSION_PARAM)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ParameterNotFound":
            raise

    scheduler = get_scheduler_client()
    try:
        scheduler.delete_schedule(Name=SCHEDULER_NAME, GroupName=SCHEDULER_GROUP)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


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


def handle_deploy(api_key: str, dbt_runner: str = "duckdb") -> tuple[int, dict[str, Any]]:
    """Handle deploy action."""
    if not validate_api_key(api_key):
        return 401, {"error": "Invalid password"}

    try:
        github_pat = get_secret(SECRET_GITHUB_PAT)
    except Exception as e:
        print(f"Error retrieving GitHub PAT: {e}")
        return 500, {"error": "Failed to retrieve GitHub credentials"}

    path = f"/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/dispatches"
    body = {"ref": "main", "inputs": {"action": "deploy-platform", "dbt_runner": dbt_runner}}

    status_code, response_data = github_api_request("POST", path, github_pat, body)

    # GitHub returns 204 No Content on successful workflow dispatch
    if status_code == 204:
        # Create deploying session (no deadline yet — countdown starts on activate)
        now = int(time.time())
        try:
            create_session_deploying(deployed_at=now)
        except Exception as e:
            print(f"Warning: Failed to create deploying session: {e}")

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


def handle_session_status() -> tuple[int, dict[str, Any]]:
    """Handle session-status action (no auth required)."""
    try:
        session = get_session()
    except Exception as e:
        print(f"Error reading session: {e}")
        return 500, {"error": "Failed to read session state"}

    if session is None:
        return 200, {"active": False}

    now = int(time.time())
    deployed_at = session["deployed_at"]
    deadline = session.get("deadline")
    tearing_down = session.get("tearing_down", False)
    elapsed_seconds = now - deployed_at
    elapsed_hours = elapsed_seconds / 3600.0
    cost_so_far = round(elapsed_hours * PLATFORM_COST_PER_HOUR, 2)

    # Tearing down takes priority over all other states
    if tearing_down:
        tearing_down_at = session.get("tearing_down_at", deadline or deployed_at)
        if now - tearing_down_at > TEARDOWN_TIMEOUT_SECONDS:
            # Stale flag — teardown workflow likely finished but cleanup failed
            delete_session()
            return 200, {"active": False}

        return 200, {
            "active": False,
            "deploying": False,
            "tearing_down": True,
            "tearing_down_at": tearing_down_at,
            "deployed_at": deployed_at,
            "elapsed_seconds": elapsed_seconds,
            "cost_so_far": cost_so_far,
        }

    # Session exists but countdown not yet started (deploying)
    if deadline is None:
        if elapsed_seconds > DEPLOYING_TIMEOUT_SECONDS:
            # Stale deploying session — deploy likely failed or was abandoned
            delete_session()
            return 200, {"active": False}

        return 200, {
            "active": False,
            "deploying": True,
            "deployed_at": deployed_at,
            "elapsed_seconds": elapsed_seconds,
            "cost_so_far": cost_so_far,
        }

    # Session has a deadline — normal countdown
    remaining = max(0, deadline - now)
    return 200, {
        "active": remaining > 0,
        "deploying": False,
        "remaining_seconds": remaining,
        "deployed_at": deployed_at,
        "deadline": deadline,
        "elapsed_seconds": elapsed_seconds,
        "cost_so_far": cost_so_far,
    }


def handle_teardown_status() -> tuple[int, dict[str, Any]]:
    """Handle teardown-status action (no auth required).

    Returns step-level progress for an in-progress teardown workflow.
    """
    try:
        session = get_session()
    except Exception as e:
        print(f"Error reading session: {e}")
        return 200, {"tearing_down": False}

    if session is None or not session.get("tearing_down", False):
        return 200, {"tearing_down": False}

    tearing_down_at = session.get("tearing_down_at")

    # Resolve run ID
    run_id = session.get("teardown_run_id")
    github_pat: str | None = None

    if run_id is None:
        # Try to find the run from recent workflow runs
        try:
            github_pat = get_secret(SECRET_GITHUB_PAT)
            path = (
                f"/repos/{GITHUB_REPO}/actions/workflows/"
                f"{GITHUB_TEARDOWN_WORKFLOW}/runs?per_page=3"
            )
            status_code, response_data = github_api_request("GET", path, github_pat)

            if status_code == 200:
                cutoff = (tearing_down_at or 0) - 60
                for run in response_data.get("workflow_runs", []):
                    # Parse created_at ISO timestamp
                    from datetime import datetime

                    created_at_str = run.get("created_at", "")
                    try:
                        created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        created_ts = int(created_dt.timestamp())
                    except (ValueError, AttributeError):
                        continue

                    if created_ts >= cutoff:
                        run_id = run["id"]
                        # Cache run_id in SSM for future polls
                        try:
                            session["teardown_run_id"] = run_id
                            get_ssm_client().put_parameter(
                                Name=SSM_SESSION_PARAM,
                                Value=json.dumps(session),
                                Type="String",
                                Overwrite=True,
                            )
                        except Exception as e:
                            print(f"Warning: Failed to cache run_id: {e}")
                        break
        except Exception as e:
            print(f"Warning: Failed to query teardown runs: {e}")

    # Build default pending steps
    pending_steps = [{"name": label, "status": "pending"} for label in TEARDOWN_UI_LABELS]

    if run_id is None:
        return 200, {
            "tearing_down": True,
            "run_id": None,
            "workflow_status": "queued",
            "workflow_conclusion": None,
            "current_step": -1,
            "total_steps": len(TEARDOWN_UI_LABELS),
            "steps": pending_steps,
        }

    # Fetch job steps from GitHub API
    try:
        if github_pat is None:
            github_pat = get_secret(SECRET_GITHUB_PAT)
        path = f"/repos/{GITHUB_REPO}/actions/runs/{run_id}/jobs"
        status_code, response_data = github_api_request("GET", path, github_pat)

        if status_code != 200:
            print(f"GitHub jobs API returned {status_code}: {response_data}")
            return 200, {
                "tearing_down": True,
                "run_id": run_id,
                "workflow_status": "in_progress",
                "workflow_conclusion": None,
                "current_step": -1,
                "total_steps": len(TEARDOWN_UI_LABELS),
                "steps": pending_steps,
            }

        jobs = response_data.get("jobs", [])
        if not jobs:
            return 200, {
                "tearing_down": True,
                "run_id": run_id,
                "workflow_status": "queued",
                "workflow_conclusion": None,
                "current_step": -1,
                "total_steps": len(TEARDOWN_UI_LABELS),
                "steps": pending_steps,
            }

        job = jobs[0]
        workflow_status = job.get("status", "queued")
        workflow_conclusion = job.get("conclusion")
        job_steps = job.get("steps", [])

        # Map workflow steps to UI steps using TEARDOWN_STEP_RANGES
        ui_steps: list[dict[str, str]] = []
        current_step = -1

        for ui_idx, (start, end) in enumerate(TEARDOWN_STEP_RANGES):
            range_steps = job_steps[start:end]

            if not range_steps:
                ui_steps.append({"name": TEARDOWN_UI_LABELS[ui_idx], "status": "pending"})
                continue

            all_completed = all(s.get("status") == "completed" for s in range_steps)
            any_in_progress = any(s.get("status") == "in_progress" for s in range_steps)

            if all_completed:
                ui_steps.append({"name": TEARDOWN_UI_LABELS[ui_idx], "status": "completed"})
            elif any_in_progress:
                ui_steps.append({"name": TEARDOWN_UI_LABELS[ui_idx], "status": "in_progress"})
                current_step = ui_idx
            else:
                ui_steps.append({"name": TEARDOWN_UI_LABELS[ui_idx], "status": "pending"})

        # If no step is in_progress but some are completed, current_step is the
        # first non-completed step (or last step if all completed)
        if current_step == -1:
            for i, step in enumerate(ui_steps):
                if step["status"] != "completed":
                    current_step = i
                    break
            else:
                # All completed
                current_step = len(ui_steps) - 1

        return 200, {
            "tearing_down": True,
            "run_id": run_id,
            "workflow_status": workflow_status,
            "workflow_conclusion": workflow_conclusion,
            "current_step": current_step,
            "total_steps": len(TEARDOWN_UI_LABELS),
            "steps": ui_steps,
        }

    except Exception as e:
        print(f"Error fetching teardown job steps: {e}")
        return 200, {
            "tearing_down": True,
            "run_id": run_id,
            "workflow_status": "in_progress",
            "workflow_conclusion": None,
            "current_step": -1,
            "total_steps": len(TEARDOWN_UI_LABELS),
            "steps": pending_steps,
        }


def handle_activate_session(api_key: str) -> tuple[int, dict[str, Any]]:
    """Handle activate-session action.

    Called by frontend when health check passes. Sets the deadline and
    schedules auto-teardown. Idempotent — returns existing values if
    deadline is already set.
    """
    if not validate_api_key(api_key):
        return 401, {"error": "Invalid password"}

    session = get_session()
    if session is None:
        return 404, {"error": "No active session"}

    # Idempotent: if deadline already set, return existing values
    if session.get("deadline") is not None:
        now = int(time.time())
        remaining = max(0, session["deadline"] - now)
        return 200, {
            "success": True,
            "remaining_seconds": remaining,
            "deadline": session["deadline"],
        }

    # Set deadline and schedule teardown
    now = int(time.time())
    deadline = now + (SESSION_STEP_MINUTES * 60)
    try:
        create_session(deployed_at=session["deployed_at"], deadline=deadline)
    except Exception as e:
        print(f"Error activating session: {e}")
        return 500, {"error": "Failed to activate session"}

    return 200, {
        "success": True,
        "remaining_seconds": SESSION_STEP_MINUTES * 60,
        "deadline": deadline,
    }


def handle_extend_session(api_key: str) -> tuple[int, dict[str, Any]]:
    """Handle extend-session action."""
    if not validate_api_key(api_key):
        return 401, {"error": "Invalid password"}

    session = get_session()
    if session is None:
        return 404, {"error": "No active session"}

    if session.get("deadline") is None:
        return 400, {"error": "Session not yet activated"}

    now = int(time.time())
    remaining = session["deadline"] - now
    step = SESSION_STEP_MINUTES * 60

    if remaining + step > MAX_REMAINING_SECONDS:
        return 400, {"error": "Cannot extend beyond 2 hours remaining"}

    new_deadline = session["deadline"] + step
    try:
        update_session_deadline(new_deadline)
    except Exception as e:
        print(f"Error extending session: {e}")
        return 500, {"error": "Failed to extend session"}

    return 200, {
        "success": True,
        "remaining_seconds": max(0, new_deadline - now),
        "deadline": new_deadline,
    }


def handle_shrink_session(api_key: str) -> tuple[int, dict[str, Any]]:
    """Handle shrink-session action."""
    if not validate_api_key(api_key):
        return 401, {"error": "Invalid password"}

    session = get_session()
    if session is None:
        return 404, {"error": "No active session"}

    if session.get("deadline") is None:
        return 400, {"error": "Session not yet activated"}

    now = int(time.time())
    remaining = session["deadline"] - now
    step = SESSION_STEP_MINUTES * 60

    if remaining < step:
        return 400, {"error": "Cannot shrink below 0 minutes remaining"}

    new_deadline = session["deadline"] - step
    try:
        update_session_deadline(new_deadline)
    except Exception as e:
        print(f"Error shrinking session: {e}")
        return 500, {"error": "Failed to shrink session"}

    return 200, {
        "success": True,
        "remaining_seconds": max(0, new_deadline - now),
        "deadline": new_deadline,
    }


def handle_auto_teardown() -> tuple[int, dict[str, Any]]:
    """Handle auto-teardown action (internal, triggered by EventBridge)."""
    # Check if a deploy is currently in progress
    try:
        github_pat = get_secret(SECRET_GITHUB_PAT)
        path = f"/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/runs?per_page=1"
        status_code, response_data = github_api_request("GET", path, github_pat)

        if status_code == 200:
            runs = response_data.get("workflow_runs", [])
            if runs and runs[0].get("status") == "in_progress":
                # Deploy in progress — reschedule 5 min later
                new_deadline = int(time.time()) + RESCHEDULE_DELAY_SECONDS
                try:
                    _upsert_schedule(new_deadline)
                    session = get_session()
                    if session is not None:
                        update_session_deadline(new_deadline)
                except Exception as e:
                    print(f"Warning: Failed to reschedule: {e}")
                return 200, {"action": "rescheduled", "reason": "deploy_in_progress"}
    except Exception as e:
        print(f"Warning: Failed to check deploy status: {e}")

    # Set tearing_down flag so frontend shows teardown status
    try:
        session = get_session()
        if session is not None:
            session["tearing_down"] = True
            session["tearing_down_at"] = int(time.time())
            get_ssm_client().put_parameter(
                Name=SSM_SESSION_PARAM,
                Value=json.dumps(session),
                Type="String",
                Overwrite=True,
            )
    except Exception as e:
        print(f"Warning: Failed to set tearing_down flag: {e}")

    # Delete EventBridge schedule to prevent re-triggers
    scheduler = get_scheduler_client()
    try:
        scheduler.delete_schedule(Name=SCHEDULER_NAME, GroupName=SCHEDULER_GROUP)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            print(f"Warning: Failed to delete schedule: {e}")

    # Trigger teardown workflow
    try:
        github_pat = get_secret(SECRET_GITHUB_PAT)
        path = f"/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_TEARDOWN_WORKFLOW}/dispatches"
        body = {"ref": "main"}
        status_code, response_data = github_api_request("POST", path, github_pat, body)

        if status_code == 204:
            print("Teardown workflow triggered successfully")
        else:
            print(f"Teardown trigger returned {status_code}: {response_data}")
    except Exception as e:
        print(f"Error triggering teardown: {e}")
        return 500, {"error": "Failed to trigger teardown"}

    # Do NOT delete session — teardown workflow cleanup step handles it.
    # The SSM parameter stays with tearing_down=True so frontend shows status.

    return 200, {"action": "teardown_triggered"}


def _check_service(service_id: str, url: str) -> tuple[str, bool]:
    """Check if a single service is healthy. Returns (service_id, is_healthy)."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=HEALTH_CHECK_TIMEOUT):
            return service_id, True
    except Exception:
        return service_id, False


def handle_service_health() -> tuple[int, dict[str, Any]]:
    """Check health of all platform services in parallel."""
    results: dict[str, bool] = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(SERVICE_HEALTH_ENDPOINTS)
    ) as executor:
        futures = {
            executor.submit(_check_service, sid, url): sid
            for sid, url in SERVICE_HEALTH_ENDPOINTS.items()
        }
        for future in concurrent.futures.as_completed(futures):
            service_id, healthy = future.result()
            results[service_id] = healthy

    return 200, {"services": results}


def get_response_headers() -> dict[str, str]:
    """Get standard response headers.

    CORS headers are handled by AWS Lambda Function URL configuration
    (defined in Terraform). Adding them here would duplicate the header
    values, which browsers reject.

    Returns:
        Dict of non-CORS response headers
    """
    return {
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
        if action not in NO_AUTH_ACTIONS and not api_key:
            return {"error": "Missing required field: api_key"}

        no_auth_handlers: dict[str, Any] = {
            "session-status": handle_session_status,
            "auto-teardown": handle_auto_teardown,
            "service-health": handle_service_health,
            "teardown-status": handle_teardown_status,
        }
        auth_handlers: dict[str, Any] = {
            "validate": handle_validate,
            "deploy": handle_deploy,
            "status": handle_status,
            "activate-session": handle_activate_session,
            "extend-session": handle_extend_session,
            "shrink-session": handle_shrink_session,
        }

        if action in no_auth_handlers:
            _, response_body = no_auth_handlers[action]()
            return response_body
        if action == "deploy":
            dbt_runner = event.get("dbt_runner", "duckdb")
            if dbt_runner not in ("duckdb", "glue"):
                return {"error": "Invalid dbt_runner: must be 'duckdb' or 'glue'"}
            _, response_body = handle_deploy(api_key, dbt_runner)
            return response_body
        if action in auth_handlers:
            _, response_body = auth_handlers[action](api_key)
            return response_body

        return {
            "error": f"Unknown action: {action}",
            "valid_actions": [
                "validate",
                "deploy",
                "status",
                "session-status",
                "service-health",
                "teardown-status",
                "activate-session",
                "extend-session",
                "shrink-session",
            ],
        }

    # Function URL invocation: event is a full HTTP request envelope.
    # CORS is handled by AWS Lambda Function URL configuration (Terraform).
    # Preflight OPTIONS requests are handled automatically by the Function URL.
    response_headers = get_response_headers()

    # Parse request body
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": response_headers,
            "body": json.dumps({"error": "Invalid JSON in request body"}),
        }

    # Extract action and api_key
    action = body.get("action")
    api_key = body.get("api_key")

    # Validate required fields
    if not action:
        return {
            "statusCode": 400,
            "headers": response_headers,
            "body": json.dumps({"error": "Missing required field: action"}),
        }

    if action not in NO_AUTH_ACTIONS and not api_key:
        return {
            "statusCode": 400,
            "headers": response_headers,
            "body": json.dumps({"error": "Missing required field: api_key"}),
        }

    # Route to appropriate handler
    no_auth_handlers: dict[str, Any] = {
        "session-status": handle_session_status,
        "auto-teardown": handle_auto_teardown,
        "service-health": handle_service_health,
        "teardown-status": handle_teardown_status,
    }
    auth_handlers: dict[str, Any] = {
        "validate": handle_validate,
        "deploy": handle_deploy,
        "status": handle_status,
        "activate-session": handle_activate_session,
        "extend-session": handle_extend_session,
        "shrink-session": handle_shrink_session,
    }

    if action in no_auth_handlers:
        status_code, response_body = no_auth_handlers[action]()
    elif action == "deploy":
        dbt_runner = body.get("dbt_runner", "duckdb")
        if dbt_runner not in ("duckdb", "glue"):
            return {
                "statusCode": 400,
                "headers": response_headers,
                "body": json.dumps({"error": "Invalid dbt_runner: must be 'duckdb' or 'glue'"}),
            }
        status_code, response_body = handle_deploy(api_key, dbt_runner)
    elif action in auth_handlers:
        status_code, response_body = auth_handlers[action](api_key)
    else:
        status_code = 400
        response_body = {
            "error": f"Unknown action: {action}",
            "valid_actions": [
                "validate",
                "deploy",
                "status",
                "session-status",
                "service-health",
                "teardown-status",
                "activate-session",
                "extend-session",
                "shrink-session",
            ],
        }

    return {
        "statusCode": status_code,
        "headers": response_headers,
        "body": json.dumps(response_body),
    }
