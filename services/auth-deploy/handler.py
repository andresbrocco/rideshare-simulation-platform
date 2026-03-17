import base64
import concurrent.futures
import hmac
import json
import os
import secrets
import time
import urllib.request
import urllib.error
from datetime import timezone
from datetime import datetime
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Constants
GITHUB_API_BASE = "https://api.github.com"
GITHUB_REPO = "andresbrocco/rideshare-simulation-platform"
GITHUB_WORKFLOW = "deploy-platform.yml"
GITHUB_API_VERSION = "2022-11-28"
REQUEST_TIMEOUT = 10  # seconds

# Secret keys
SECRET_API_KEY = "rideshare/api-key"
SECRET_GITHUB_PAT = "rideshare/github-pat"
SECRET_ADMIN_USER = "rideshare/admin-user"

# Session management constants
SSM_SESSION_PARAM = "/rideshare/session/deadline"
SCHEDULER_GROUP = "default"
SCHEDULER_NAME = "rideshare-auto-teardown"
GITHUB_TEARDOWN_WORKFLOW = "teardown-platform.yml"
SESSION_STEP_MINUTES = 45
MAX_REMAINING_SECONDS = 2 * 3600  # 2 hours
PLATFORM_COST_PER_HOUR = 0.31
RESCHEDULE_DELAY_SECONDS = 300  # 5 min
TEARDOWN_TIMEOUT_SECONDS = 15 * 60  # 15 min — auto-clear stale tearing_down flag
DEPLOYING_TIMEOUT_SECONDS = 30 * 60  # 30 min — auto-clear stale deploying session

SIMULATION_START_DEFAULTS: dict[str, int] = {
    "immediate_drivers": 50,
    "immediate_riders": 50,
    "scheduled_drivers": 150,
    "scheduled_riders": 1950,
}
SIMULATION_API_TIMEOUT = 20  # seconds per request

# SES welcome email
SES_FROM_ADDRESS_ENV = "SES_FROM_ADDRESS"
SES_FROM_ADDRESS_DEFAULT = "noreply@ridesharing.portfolio.andresbrocco.com"
SES_FROM_NAME_ENV = "SES_FROM_NAME"
SES_FROM_NAME_DEFAULT = "Rideshare Platform"
SES_REPLY_TO_ADDRESS_ENV = "SES_REPLY_TO_ADDRESS"

SERVICE_INFO: dict[str, dict[str, str]] = {
    "Control Panel": {
        "url": "https://control-panel.ridesharing.portfolio.andresbrocco.com",
        "desc": "Real-time simulation map — watch drivers and riders move across São Paulo",
    },
    "Airflow": {
        "url": "https://airflow.ridesharing.portfolio.andresbrocco.com/login",
        "desc": "4 DAGs orchestrating Bronze → Silver → Gold transformations",
    },
    "Grafana": {
        "url": "https://grafana.ridesharing.portfolio.andresbrocco.com",
        "desc": "Multi-datasource dashboards — metrics, logs, traces, and BI analytics",
    },
}

SERVICE_LOGIN_URLS: dict[str, str] = {name: info["url"] for name, info in SERVICE_INFO.items()}

LANDING_PAGE_URL = "https://ridesharing.portfolio.andresbrocco.com"
EMAIL_ICONS_BASE_URL = f"{LANDING_PAGE_URL}/icons/email"
GITHUB_REPO_URL = "https://github.com/andresbrocco/rideshare-simulation-platform"
LINKEDIN_URL = "https://www.linkedin.com/in/andresbrocco/"

DEPLOY_PROGRESS_SERVICES = [
    "kafka",
    "redis",
    "schema-registry",
    "osrm",
    "stream-processor",
    "simulation",
    "bronze-ingestion",
    "airflow",
    "glue-catalog",
    "trino",
    "prometheus",
    "grafana",
    "loki",
    "tempo",
    "control-panel",
    "performance-controller",
]

SERVICE_HEALTH_ENDPOINTS: dict[str, str] = {
    "simulation_api": "https://api.ridesharing.portfolio.andresbrocco.com/health",
    "grafana": "https://grafana.ridesharing.portfolio.andresbrocco.com/api/health",
    "airflow": "https://airflow.ridesharing.portfolio.andresbrocco.com/api/v2/monitor/health",
    "trino": "https://trino.ridesharing.portfolio.andresbrocco.com/v1/info",
    "prometheus": "https://prometheus.ridesharing.portfolio.andresbrocco.com/-/healthy",
}
HEALTH_CHECK_TIMEOUT = 5  # seconds

NO_AUTH_ACTIONS = {
    "session-status",
    "auto-teardown",
    "service-health",
    "teardown-status",
    "get-deploy-progress",
    "provision-visitor",
    "visitor-login",
    "extend-session",
    "shrink-session",
}

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


def _get_dynamodb_client() -> boto3.client:
    """Get DynamoDB client configured for LocalStack or AWS."""
    config = Config(
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        signature_version="v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )

    endpoint_url = None
    if os.environ.get("LOCALSTACK_HOSTNAME"):
        endpoint_url = f"http://{os.environ['LOCALSTACK_HOSTNAME']}:4566"

    return boto3.client("dynamodb", config=config, endpoint_url=endpoint_url)


def _store_visitor_dynamodb(
    email: str,
    password: str,
    provisioned_services: list[str],
    consent_timestamp: str,
) -> None:
    """Store visitor record in DynamoDB after successful provisioning.

    Writes email, consent timestamp, provisioned service list, PBKDF2 password
    hash, and created-at timestamp.  DynamoDB failures are logged but do not
    roll back any already-completed service provisioning.

    Args:
        email: Visitor email address (partition key).
        password: Visitor plaintext password — stored as a PBKDF2-SHA256 hash only.
        provisioned_services: Names of services that were provisioned successfully.
        consent_timestamp: ISO-8601 timestamp of visitor consent, supplied by the caller.
    """
    password_hash = _hash_password_pbkdf2(password)
    created_at = datetime.now(timezone.utc).isoformat()
    table_name = os.environ.get("VISITOR_TABLE_NAME", "rideshare-visitors")

    # DynamoDB String Set (SS) requires at least one element; fall back to an
    # empty List (L) when no services were provisioned.
    services_attr: dict[str, Any]
    if provisioned_services:
        services_attr = {"SS": provisioned_services}
    else:
        services_attr = {"L": []}

    # Attempt KMS encryption of the plaintext password so it can be recovered
    # after platform redeploy.  KMS may not be available in dev/LocalStack —
    # failure is logged but does not abort the DynamoDB write.
    item: dict[str, Any] = {
        "email": {"S": email},
        "consent_timestamp": {"S": consent_timestamp},
        "provisioned_services": services_attr,
        "password_hash": {"S": password_hash},
        "created_at": {"S": created_at},
    }

    try:
        encrypted_password = _encrypt_password(password)
        item["encrypted_password"] = {"S": encrypted_password}
    except Exception as kms_exc:
        print(
            f"KMS password encryption failed (non-fatal, encrypted_password not stored): {kms_exc}"
        )

    client = _get_dynamodb_client()
    client.put_item(TableName=table_name, Item=item)


def _get_kms_client() -> boto3.client:
    """Get KMS client configured for LocalStack or AWS."""
    config = Config(
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        signature_version="v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )

    endpoint_url = None
    if os.environ.get("LOCALSTACK_HOSTNAME"):
        endpoint_url = f"http://{os.environ['LOCALSTACK_HOSTNAME']}:4566"

    return boto3.client("kms", config=config, endpoint_url=endpoint_url)


def _encrypt_password(plaintext: str) -> str:
    """Encrypt a plaintext password using KMS and return base64-encoded ciphertext.

    The KMS key ARN is read from the ``KMS_VISITOR_PASSWORD_KEY`` environment
    variable.  If the variable is unset, an ``EnvironmentError`` is raised so
    callers can decide whether to treat the failure as fatal.

    Args:
        plaintext: The plaintext password to encrypt.

    Returns:
        Base64-encoded KMS ciphertext blob (safe to store in DynamoDB).

    Raises:
        EnvironmentError: If ``KMS_VISITOR_PASSWORD_KEY`` is not configured.
        ClientError: If KMS encrypt call fails.
    """
    key_arn = os.environ.get("KMS_VISITOR_PASSWORD_KEY", "")
    if not key_arn:
        raise EnvironmentError("KMS_VISITOR_PASSWORD_KEY environment variable is not set")

    client = _get_kms_client()
    response = client.encrypt(KeyId=key_arn, Plaintext=plaintext.encode())
    return base64.b64encode(response["CiphertextBlob"]).decode()


def _decrypt_password(ciphertext_b64: str) -> str:
    """Decrypt a base64-encoded KMS ciphertext and return the plaintext password.

    Args:
        ciphertext_b64: Base64-encoded KMS ciphertext blob as stored in DynamoDB.

    Returns:
        Plaintext password string.

    Raises:
        ClientError: If KMS decrypt call fails.
        Exception: For any other decryption error.
    """
    ciphertext = base64.b64decode(ciphertext_b64)
    client = _get_kms_client()
    response = client.decrypt(CiphertextBlob=ciphertext)
    return response["Plaintext"].decode()


def _get_ses_client() -> boto3.client:
    """Get SES client configured for LocalStack or AWS."""
    config = Config(
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        signature_version="v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )

    endpoint_url = None
    if os.environ.get("LOCALSTACK_HOSTNAME"):
        endpoint_url = f"http://{os.environ['LOCALSTACK_HOSTNAME']}:4566"

    return boto3.client("ses", config=config, endpoint_url=endpoint_url)


def _build_welcome_email(email: str, name: str, password: str) -> tuple[str, str, str]:
    """Build welcome email content with credentials and service URLs.

    Returns:
        Tuple of (subject, text_body, html_body).
    """
    subject = f"Hey {name} — your access to my rideshare platform"

    # --- Plain text body ---
    service_lines_text = "\n".join(
        f"  {i}. {svc}: {info['url']}\n     {info['desc']}"
        for i, (svc, info) in enumerate(SERVICE_INFO.items(), 1)
    )

    text_body = (
        f"Hey {name},\n\n"
        f"Thanks for checking out my portfolio — really glad you're here.\n\n"
        f"Your credentials:\n\n"
        f"  Email:    {email}\n"
        f"  Password: {password}\n\n"
        f"Use them to log in to any of these services:\n\n"
        f"{service_lines_text}\n\n"
        f"About me: I'm André Sbrocco, a data engineer based in São Paulo, Brazil. "
        f"I built this rideshare simulation platform to demonstrate event-driven "
        f"pipelines, a medallion lakehouse, and real-time analytics in one live system.\n\n"
        f"What to explore:\n\n"
        f'  1. Hit "Deploy" on the landing page ({LANDING_PAGE_URL}), then open\n'
        f"     Control Panel for the live map\n"
        f"  2. Check Grafana dashboards — Kafka throughput, driver utilization,\n"
        f"     pipeline health\n"
        f"  3. Run SQL in Trino against the Gold star schema\n\n"
        f"Note: Your accounts are active now. If the platform is currently "
        f'offline, hit "Deploy" on the landing page — services typically start '
        f"within about 20 minutes.\n\n"
        f"If you have questions or just want to chat about the architecture, "
        f"hit reply — it goes straight to my inbox.\n\n"
        f"Cheers,\n"
        f"André\n\n"
        f"GitHub: {GITHUB_REPO_URL}\n"
        f"LinkedIn: {LINKEDIN_URL}"
    )

    # --- HTML body (table-based, inline styles, email-safe) ---
    font = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

    # Service icon filenames (hosted PNGs on CloudFront)
    _SERVICE_ICON_FILES: dict[str, str] = {
        "Control Panel": "control-panel.png",
        "Grafana": "grafana.png",
        "Airflow": "airflow.png",
        "Trino": "trino.png",
        "MinIO": "minio.png",
        "Simulation API": "simulation-api.png",
    }

    # Car favicon icon for landing page link (hosted PNG on CloudFront)
    car_icon = (
        f'<img src="{EMAIL_ICONS_BASE_URL}/car.png"'
        ' width="16" height="16" alt=""'
        ' style="vertical-align:middle;margin-right:4px;">'
    )

    service_rows_html = ""
    for svc, info in SERVICE_INFO.items():
        icon_file = _SERVICE_ICON_FILES.get(svc)
        icon = (
            (
                f'<img src="{EMAIL_ICONS_BASE_URL}/{icon_file}"'
                f' width="18" height="18" alt=""'
                f' style="vertical-align:middle;margin-right:8px;">'
            )
            if icon_file
            else ""
        )
        service_rows_html += (
            f'<tr><td style="padding:8px 16px;font-family:{font};">'
            f"{icon}"
            f'<a href="{info["url"]}" style="color:#00ff88;font-weight:bold;text-decoration:none;">{svc}</a>'
            f'<br><span style="color:#949b99;font-size:13px;padding-left:26px;display:inline-block;">{info["desc"]}</span>'
            f"</td></tr>"
        )

    html_body = (
        # DOCTYPE + charset
        f'<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        f'<body style="margin:0;padding:0;">'
        # Outer wrapper
        f'<table width="100%" bgcolor="#0a0c0b" cellpadding="0" cellspacing="0" '
        f'style="font-family:{font};"><tr><td align="center" style="padding:32px 16px;">'
        # Inner card
        f'<table width="600" bgcolor="#131716" cellpadding="0" cellspacing="0" '
        f'style="border-radius:8px;overflow:hidden;border:1px solid #1e2422;">'
        # Accent bar
        f'<tr><td bgcolor="#00ff88" style="height:4px;font-size:0;line-height:0;">&nbsp;</td></tr>'
        # Project name header
        f'<tr><td style="padding:24px 32px 0;font-family:{font};font-size:20px;'
        f'font-weight:bold;color:#00ff88;">Rideshare Simulation Platform</td></tr>'
        # Greeting
        f'<tr><td style="padding:16px 32px 0;font-family:{font};font-size:15px;color:#c5cac8;">'
        f"<p>Hey {name},</p>"
        f"<p>Thanks for checking out my portfolio — really glad you're here.</p>"
        f"</td></tr>"
        # Credentials box
        f'<tr><td style="padding:8px 32px;">'
        f'<table width="100%" bgcolor="#1a1d1c" cellpadding="0" cellspacing="0" '
        f'style="border:1px solid #0d2b18;border-radius:6px;">'
        f'<tr><td style="padding:16px 20px;font-family:{font};font-size:14px;color:#c5cac8;">'
        f'<strong style="font-size:15px;">Your credentials</strong><br><br>'
        f'<span style="font-family:monospace;color:#00ff88;">Email:&nbsp;&nbsp;&nbsp;&nbsp;{email}<br>'
        f"Password:&nbsp;{password}</span>"
        f"</td></tr></table></td></tr>"
        # Services
        f'<tr><td style="padding:8px 32px;font-family:{font};font-size:14px;color:#c5cac8;">'
        f"<p>Use them to log in to any of these services:</p>"
        f'<table width="100%" cellpadding="0" cellspacing="0">'
        f"{service_rows_html}"
        f"</table></td></tr>"
        # About me
        f'<tr><td style="padding:8px 32px;font-family:{font};font-size:14px;color:#c5cac8;">'
        f"<p>I'm André Sbrocco, a data engineer based in São Paulo, Brazil. "
        f"I built this rideshare simulation platform to demonstrate event-driven "
        f"pipelines, a medallion lakehouse, and real-time analytics in one live system.</p>"
        f"</td></tr>"
        # What to explore
        f'<tr><td style="padding:8px 32px;font-family:{font};font-size:14px;color:#c5cac8;">'
        f"<p><strong>What to explore:</strong></p>"
        f'<ol style="padding-left:20px;margin:8px 0;line-height:1.7;">'
        f'<li>Hit "Deploy" on the {car_icon}<a href="{LANDING_PAGE_URL}" style="color:#00ff88;">landing page</a>, '
        f"then open Control Panel for the live map</li>"
        f"<li>Check Grafana dashboards — Kafka throughput, driver utilization, pipeline health</li>"
        f"<li>Run SQL in Trino against the Gold star schema</li>"
        f"</ol></td></tr>"
        # Deploy callout
        f'<tr><td style="padding:8px 32px 16px;">'
        f'<table width="100%" bgcolor="#1a1d1c" cellpadding="0" cellspacing="0" '
        f'style="border-left:4px solid #00ff88;border-radius:4px;">'
        f'<tr><td style="padding:12px 16px;font-family:{font};font-size:13px;color:#c5cac8;">'
        f"<strong>Note:</strong> Your accounts are active now. If the platform is currently "
        f'offline, hit "Deploy" on the landing page — services typically start '
        f"within about 20 minutes."
        f"</td></tr></table></td></tr>"
        # Reply invitation
        f'<tr><td style="padding:0 32px 24px;font-family:{font};font-size:14px;color:#c5cac8;">'
        f"<p>If you have questions or just want to chat about the architecture, "
        f"hit reply — it goes straight to my inbox.</p>"
        f"<p>Cheers,<br>André</p>"
        f"</td></tr>"
        # Close inner card
        f"</table>"
        # Footer
        f'<table width="600" cellpadding="0" cellspacing="0" align="center">'
        f'<tr><td align="center" style="padding:16px 32px;font-family:{font};font-size:12px;color:#6b7371;">'
        f'<a href="{GITHUB_REPO_URL}" style="color:#949b99;text-decoration:none;">GitHub</a>'
        f' <span style="color:#6b7371;">&nbsp;·&nbsp;</span> '
        f'<a href="{LINKEDIN_URL}" style="color:#949b99;text-decoration:none;">LinkedIn</a>'
        f"</td></tr></table>"
        # Close outer wrapper
        f"</td></tr></table>"
        # Close doc shell
        f"</body></html>"
    )

    return subject, text_body, html_body


def _send_welcome_email(email: str, name: str, password: str) -> bool:
    """Send welcome email via SES with credentials and service URLs.

    Email failures are non-fatal — returns False on error without raising.
    """
    from_address = os.environ.get(SES_FROM_ADDRESS_ENV, SES_FROM_ADDRESS_DEFAULT)
    from_name = os.environ.get(SES_FROM_NAME_ENV, SES_FROM_NAME_DEFAULT)
    source = f"{from_name} <{from_address}>"
    reply_to = os.environ.get(SES_REPLY_TO_ADDRESS_ENV)
    subject, text_body, html_body = _build_welcome_email(email, name, password)
    client = _get_ses_client()
    try:
        send_kwargs: dict[str, object] = {
            "Source": source,
            "Destination": {"ToAddresses": [email]},
            "Message": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        }
        if reply_to:
            send_kwargs["ReplyToAddresses"] = [reply_to]
        client.send_email(**send_kwargs)
        print(f"Welcome email sent to {email}")
        return True
    except Exception as exc:
        print(f"Welcome email failed (non-fatal): {exc}")
        return False


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


def get_secret_json(secret_id: str) -> dict[str, str]:
    """Retrieve and parse a JSON secret from Secrets Manager.

    Args:
        secret_id: Secret name or ARN.

    Returns:
        Parsed JSON dict.

    Raises:
        ClientError: If secret cannot be retrieved.
        ValueError: If secret is not valid JSON dict.
    """
    client = get_secrets_client()
    response = client.get_secret_value(SecretId=secret_id)

    if "SecretString" not in response:
        raise ValueError(f"Secret {secret_id} is not a string secret")

    parsed = json.loads(response["SecretString"])
    if not isinstance(parsed, dict):
        raise ValueError(f"Secret {secret_id} is not a JSON object")
    return parsed


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


def _simulation_api_request(
    method: str,
    path: str,
    api_key: str,
    body: dict[str, Any] | None = None,
    timeout: int = SIMULATION_API_TIMEOUT,
) -> tuple[int, dict[str, Any]]:
    """Make authenticated request to the Simulation API.

    Args:
        method: HTTP method (GET, POST)
        path: API path (e.g., "/simulation/start")
        api_key: Simulation API key (X-API-Key header)
        body: Request body for POST requests
        timeout: Request timeout in seconds

    Returns:
        Tuple of (status_code, response_data)
    """
    base_url = os.environ.get(
        "SIMULATION_API_URL", "https://api.ridesharing.portfolio.andresbrocco.com"
    )
    url = f"{base_url}{path}"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
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
        print(f"URL error calling Simulation API: {e}")
        return 502, {"message": "Failed to connect to Simulation API", "error": str(e)}
    except Exception as e:
        print(f"Unexpected error calling Simulation API: {e}")
        return 500, {"message": "Internal error calling Simulation API", "error": str(e)}


def handle_validate(api_key: str) -> tuple[int, dict[str, Any]]:
    """Handle validate action."""
    print("Action: validate")
    is_valid = validate_api_key(api_key)

    if is_valid:
        print("Action validate completed: 200")
        return 200, {"valid": True}
    print("Action validate completed: 401")
    return 401, {"valid": False, "error": "Invalid password"}


def handle_visitor_login(email: str, password: str) -> tuple[int, dict[str, Any]]:
    """Handle visitor-login action.

    Verifies visitor credentials against the PBKDF2 hash stored in DynamoDB
    during provisioning.  On success returns the admin API key so the visitor
    can trigger a deployment.

    Args:
        email: Visitor email address.
        password: Plaintext password to verify.

    Returns:
        Tuple of (status_code, response_body).
    """
    print("Action: visitor-login")

    if not email or not password:
        print("Action visitor-login completed: 400")
        return 400, {"error": "Missing required fields: email and password"}

    # Check admin credentials first (falls through to visitor flow on any failure)
    try:
        admin_secret = get_secret_json(SECRET_ADMIN_USER)
        admin_email = admin_secret.get("EMAIL", "")
        admin_password = admin_secret.get("PASSWORD", "")
        if email == admin_email and hmac.compare_digest(password, admin_password):
            api_key = get_secret(SECRET_API_KEY)
            print("Action visitor-login completed: 200 (admin)")
            return 200, {"api_key": api_key, "role": "admin", "email": email}
    except Exception as exc:
        print(f"Admin check skipped: {exc}")

    table_name = os.environ.get("VISITOR_TABLE_NAME", "rideshare-visitors")
    client = _get_dynamodb_client()

    try:
        result = client.get_item(
            TableName=table_name,
            Key={"email": {"S": email}},
        )
    except ClientError as exc:
        print(f"Action visitor-login completed: 500 (DynamoDB error: {exc})")
        return 500, {"error": "Internal error verifying credentials"}

    item = result.get("Item")
    if not item:
        print("Action visitor-login completed: 401 (email not found)")
        return 401, {"error": "Invalid email or password"}

    stored_hash = item.get("password_hash", {}).get("S", "")
    if not _verify_password_pbkdf2(password, stored_hash):
        print("Action visitor-login completed: 401 (password mismatch)")
        return 401, {"error": "Invalid email or password"}

    try:
        api_key = get_secret(SECRET_API_KEY)
    except ClientError as exc:
        print(f"Action visitor-login completed: 500 (secret retrieval error: {exc})")
        return 500, {"error": "Internal error retrieving credentials"}

    print("Action visitor-login completed: 200")
    return 200, {"api_key": api_key, "role": "viewer", "email": email}


def handle_deploy(api_key: str, dbt_runner: str = "duckdb") -> tuple[int, dict[str, Any]]:
    """Handle deploy action."""
    print("Action: deploy")
    if not validate_api_key(api_key):
        print("Action deploy completed: 401")
        return 401, {"error": "Invalid password"}

    # Guard: reject if a session already exists (prevents double-deploy race)
    existing_session = get_session()
    if existing_session is not None:
        print(f"Existing session found: {existing_session}")
        print("Action deploy completed: 409")
        return 409, {"error": "Deployment already in progress"}

    try:
        github_pat = get_secret(SECRET_GITHUB_PAT)
    except Exception as e:
        print(f"Error retrieving GitHub PAT: {e}")
        print("Action deploy completed: 500")
        return 500, {"error": "Failed to retrieve GitHub credentials"}

    path = f"/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/dispatches"
    body = {"ref": "main", "inputs": {"dbt_runner": dbt_runner}}

    status_code, response_data = github_api_request("POST", path, github_pat, body)

    # GitHub returns 204 No Content on successful workflow dispatch
    if status_code == 204:
        # Create deploying session (no deadline yet — countdown starts on activate)
        now = int(time.time())
        try:
            create_session_deploying(deployed_at=now)
        except Exception as e:
            print(f"Warning: Failed to create deploying session: {e}")

        print("Action deploy completed: 200")
        return 200, {
            "triggered": True,
            "workflow": GITHUB_WORKFLOW,
            "ref": "main",
        }

    print(f"GitHub API error: {status_code} - {response_data}")
    print("Action deploy completed: 502")
    return 502, {
        "error": "Failed to trigger deployment",
        "details": response_data.get("message", "Unknown error"),
        "status_code": status_code,
    }


def handle_status(api_key: str) -> tuple[int, dict[str, Any]]:
    """Handle status action."""
    print("Action: status")
    if not validate_api_key(api_key):
        print("Action status completed: 401")
        return 401, {"error": "Invalid password"}

    try:
        github_pat = get_secret(SECRET_GITHUB_PAT)
    except Exception as e:
        print(f"Error retrieving GitHub PAT: {e}")
        print("Action status completed: 500")
        return 500, {"error": "Failed to retrieve GitHub credentials"}

    path = f"/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/runs?per_page=1"

    status_code, response_data = github_api_request("GET", path, github_pat)

    if status_code == 200:
        workflow_runs = response_data.get("workflow_runs", [])

        if not workflow_runs:
            print("Action status completed: 200")
            return 200, {"status": "idle"}

        latest_run = workflow_runs[0]
        print("Action status completed: 200")
        return 200, {
            "status": latest_run.get("status", "unknown"),
            "conclusion": latest_run.get("conclusion"),
            "run_id": latest_run.get("id"),
            "created_at": latest_run.get("created_at"),
            "html_url": latest_run.get("html_url"),
        }

    print(f"GitHub API error: {status_code} - {response_data}")
    print("Action status completed: 502")
    return 502, {
        "error": "Failed to query deployment status",
        "details": response_data.get("message", "Unknown error"),
        "status_code": status_code,
    }


def handle_session_status() -> tuple[int, dict[str, Any]]:
    """Handle session-status action (no auth required)."""
    print("Action: session-status")
    try:
        session = get_session()
    except Exception as e:
        print(f"Error reading session: {e}")
        print("Action session-status completed: 500")
        return 500, {"error": "Failed to read session state"}

    if session is None:
        print("Action session-status completed: 200 (no session)")
        return 200, {"active": False}

    print(f"Session found: {session}")
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
        teardown_elapsed = now - tearing_down_at
        if teardown_elapsed > TEARDOWN_TIMEOUT_SECONDS:
            # Stale flag — teardown workflow likely finished but cleanup failed
            print(
                f"Stale tearing_down session detected: tearing_down_at={tearing_down_at}, "
                f"elapsed={teardown_elapsed}s > timeout={TEARDOWN_TIMEOUT_SECONDS}s — clearing"
            )
            delete_session()
            print("Action session-status completed: 200")
            return 200, {"active": False}

        # GitHub API validation: if teardown workflow is no longer running, clean up
        try:
            github_pat = get_secret(SECRET_GITHUB_PAT)
            path = (
                f"/repos/{GITHUB_REPO}/actions/workflows/"
                f"{GITHUB_TEARDOWN_WORKFLOW}/runs?per_page=1"
            )
            gh_status, gh_data = github_api_request("GET", path, github_pat)
            if gh_status == 200:
                runs = gh_data.get("workflow_runs", [])
                if runs:
                    latest_status = runs[0].get("status", "")
                    print(f"Teardown workflow latest run: status={latest_status}")
                    if latest_status not in ("in_progress", "queued"):
                        print("Teardown workflow no longer running — clearing session")
                        delete_session()
                        print("Action session-status completed: 200")
                        return 200, {"active": False}
        except Exception as e:
            print(f"Warning: GitHub API check failed for teardown: {e}")

        print("Action session-status completed: 200")
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
            print(
                f"Stale deploying session detected: deployed_at={deployed_at}, "
                f"elapsed={elapsed_seconds}s > timeout={DEPLOYING_TIMEOUT_SECONDS}s — clearing"
            )
            delete_session()
            print("Action session-status completed: 200")
            return 200, {"active": False}

        # GitHub API validation: if deploy workflow failed/cancelled, clean up.
        # A successful completion is expected — the frontend will call
        # activate-session once deploy-progress reports all_ready.
        # We fetch recent runs and match by created_at near deployed_at to avoid
        # confusing deploy-frontend runs with the deploy-platform we triggered.
        try:
            github_pat = get_secret(SECRET_GITHUB_PAT)
            path = f"/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/runs?per_page=5"
            gh_status, gh_data = github_api_request("GET", path, github_pat)
            if gh_status == 200:
                from datetime import datetime

                cutoff = deployed_at - 60  # 1 min before session creation
                for run in gh_data.get("workflow_runs", []):
                    created_at_str = run.get("created_at", "")
                    try:
                        created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        created_ts = int(created_dt.timestamp())
                    except (ValueError, AttributeError):
                        continue
                    if created_ts < cutoff:
                        break  # older than session — stop searching
                    # Check if this run has a deploy-platform job (not deploy-frontend)
                    conclusion = run.get("conclusion", "")
                    status = run.get("status", "")
                    display_title = run.get("display_title", "")
                    print(
                        f"Deploy workflow run: status={status}, conclusion={conclusion}, "
                        f"title={display_title}, created={created_at_str}"
                    )
                    if conclusion in ("failure", "cancelled"):
                        print("Deploy workflow failed/cancelled — clearing deploying session")
                        delete_session()
                        print("Action session-status completed: 200")
                        return 200, {"active": False}
                    if status in ("in_progress", "queued"):
                        break  # found our running deploy — stop
        except Exception as e:
            print(f"Warning: GitHub API check failed for deploy: {e}")

        print("Action session-status completed: 200")
        return 200, {
            "active": False,
            "deploying": True,
            "deployed_at": deployed_at,
            "elapsed_seconds": elapsed_seconds,
            "cost_so_far": cost_so_far,
        }

    # Session has a deadline — normal countdown
    remaining = max(0, deadline - now)
    print("Action session-status completed: 200")
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
    print("Action: teardown-status")
    try:
        session = get_session()
    except Exception as e:
        print(f"Error reading session: {e}")
        print("Action teardown-status completed: 200")
        return 200, {"tearing_down": False}

    if session is None or not session.get("tearing_down", False):
        print("Action teardown-status completed: 200")
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
        print("Action teardown-status completed: 200")
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
            print("Action teardown-status completed: 200")
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
            print("Action teardown-status completed: 200")
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

        print("Action teardown-status completed: 200")
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
        print("Action teardown-status completed: 200")
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
    print("Action: activate-session")
    if not validate_api_key(api_key):
        print("Action activate-session completed: 401")
        return 401, {"error": "Invalid password"}

    session = get_session()
    if session is None:
        print("Action activate-session completed: 404")
        return 404, {"error": "No active session"}

    # Idempotent: if deadline already set, return existing values
    if session.get("deadline") is not None:
        now = int(time.time())
        remaining = max(0, session["deadline"] - now)
        print("Action activate-session completed: 200")
        return 200, {
            "success": True,
            "remaining_seconds": remaining,
            "deadline": session["deadline"],
        }

    # Set deadline and schedule teardown
    now = int(time.time())
    deadline = now + (SESSION_STEP_MINUTES * 60)
    try:
        update_session_deadline(deadline)
    except Exception as e:
        print(f"Error activating session: {e}")
        print("Action activate-session completed: 500")
        return 500, {"error": "Failed to activate session"}

    print("Action activate-session completed: 200")
    return 200, {
        "success": True,
        "remaining_seconds": SESSION_STEP_MINUTES * 60,
        "deadline": deadline,
    }


def handle_ensure_session(api_key: str) -> tuple[int, dict[str, Any]]:
    """Handle ensure-session action.

    Called by the deploy workflow after EKS convergence to guarantee
    auto-teardown is always scheduled, regardless of how the deploy
    was triggered. Three cases:

    1. No session exists (gh CLI path): Create full session with
       deployed_at=now, deadline=now+SESSION_STEP_MINUTES*60, and
       EventBridge schedule.
    2. Deploying session exists, no deadline (landing page, frontend
       hasn't called activate yet): Activate it — set deadline and
       schedule. Preserves original deployed_at.
    3. Session with deadline already set (landing page, frontend
       already activated): Idempotent — return existing deadline.
    """
    print("Action: ensure-session")
    if not validate_api_key(api_key):
        print("Action ensure-session completed: 401")
        return 401, {"error": "Invalid password"}

    session = get_session()
    now = int(time.time())
    deadline_seconds = SESSION_STEP_MINUTES * 60

    # Case 3: Session with deadline already set — reset deadline to now + window.
    # A re-deploy must always get a fresh auto-teardown window; the old
    # deadline may be seconds from expiry if the platform was re-deployed.
    if session is not None and session.get("deadline") is not None:
        deadline = now + deadline_seconds
        try:
            update_session_deadline(deadline)
        except Exception as e:
            print(f"Error resetting session deadline: {e}")
            print("Action ensure-session completed: 500")
            return 500, {"error": "Failed to reset session deadline"}
        print("Action ensure-session completed: 200 (deadline reset)")
        return 200, {
            "success": True,
            "remaining_seconds": deadline_seconds,
            "deadline": deadline,
            "created": False,
        }

    # Case 2: Deploying session exists without deadline — activate it
    if session is not None:
        deadline = now + deadline_seconds
        try:
            update_session_deadline(deadline)
        except Exception as e:
            print(f"Error activating deploying session: {e}")
            print("Action ensure-session completed: 500")
            return 500, {"error": "Failed to activate deploying session"}

        print("Action ensure-session completed: 200 (activated deploying)")
        return 200, {
            "success": True,
            "remaining_seconds": deadline_seconds,
            "deadline": deadline,
            "created": False,
        }

    # Case 1: No session exists — create full session
    deadline = now + deadline_seconds
    try:
        create_session(deployed_at=now, deadline=deadline)
    except Exception as e:
        print(f"Error creating session: {e}")
        print("Action ensure-session completed: 500")
        return 500, {"error": "Failed to create session"}

    print("Action ensure-session completed: 200 (created new)")
    return 200, {
        "success": True,
        "remaining_seconds": deadline_seconds,
        "deadline": deadline,
        "created": True,
    }


def handle_extend_session() -> tuple[int, dict[str, Any]]:
    """Handle extend-session action."""
    print("Action: extend-session")

    session = get_session()
    if session is None:
        print("Action extend-session completed: 404")
        return 404, {"error": "No active session"}

    if session.get("deadline") is None:
        print("Action extend-session completed: 400")
        return 400, {"error": "Session not yet activated"}

    now = int(time.time())
    remaining = session["deadline"] - now
    step = SESSION_STEP_MINUTES * 60

    if remaining + step > MAX_REMAINING_SECONDS:
        print("Action extend-session completed: 400")
        return 400, {"error": "Cannot extend beyond 2 hours remaining"}

    new_deadline = session["deadline"] + step
    try:
        update_session_deadline(new_deadline)
    except Exception as e:
        print(f"Error extending session: {e}")
        print("Action extend-session completed: 500")
        return 500, {"error": "Failed to extend session"}

    print("Action extend-session completed: 200")
    return 200, {
        "success": True,
        "remaining_seconds": max(0, new_deadline - now),
        "deadline": new_deadline,
    }


def handle_shrink_session() -> tuple[int, dict[str, Any]]:
    """Handle shrink-session action."""
    print("Action: shrink-session")

    session = get_session()
    if session is None:
        print("Action shrink-session completed: 404")
        return 404, {"error": "No active session"}

    if session.get("deadline") is None:
        print("Action shrink-session completed: 400")
        return 400, {"error": "Session not yet activated"}

    now = int(time.time())
    remaining = session["deadline"] - now
    step = SESSION_STEP_MINUTES * 60

    if remaining < step:
        print("Action shrink-session completed: 400")
        return 400, {"error": "Cannot shrink below 0 minutes remaining"}

    new_deadline = session["deadline"] - step
    try:
        update_session_deadline(new_deadline)
    except Exception as e:
        print(f"Error shrinking session: {e}")
        print("Action shrink-session completed: 500")
        return 500, {"error": "Failed to shrink session"}

    print("Action shrink-session completed: 200")
    return 200, {
        "success": True,
        "remaining_seconds": max(0, new_deadline - now),
        "deadline": new_deadline,
    }


def handle_auto_teardown() -> tuple[int, dict[str, Any]]:
    """Handle auto-teardown action (internal, triggered by EventBridge)."""
    print("Action: auto-teardown")
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
                print("Action auto-teardown completed: 200")
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
        print("Action auto-teardown completed: 500")
        return 500, {"error": "Failed to trigger teardown"}

    # Do NOT delete session — teardown workflow cleanup step handles it.
    # The SSM parameter stays with tearing_down=True so frontend shows status.

    print("Action auto-teardown completed: 200")
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
    print("Action: service-health")
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

    print("Action service-health completed: 200")
    return 200, {"services": results}


def handle_report_deploy_progress(
    api_key: str, service: str, ready: bool
) -> tuple[int, dict[str, Any]]:
    """Report a single service's deploy readiness.

    Called by the deploy workflow as each service comes online.
    """
    print("Action: report-deploy-progress")
    if not validate_api_key(api_key):
        print("Action report-deploy-progress completed: 401")
        return 401, {"error": "Invalid password"}

    if service not in DEPLOY_PROGRESS_SERVICES:
        print("Action report-deploy-progress completed: 400")
        return 400, {
            "error": f"Unknown service: {service}",
            "valid_services": DEPLOY_PROGRESS_SERVICES,
        }

    session = get_session()
    if session is None:
        print("Action report-deploy-progress completed: 404")
        return 404, {"error": "No active session"}

    deploy_progress: dict[str, bool] = session.get("deploy_progress", {})
    deploy_progress[service] = ready
    session["deploy_progress"] = deploy_progress

    client = get_ssm_client()
    client.put_parameter(
        Name=SSM_SESSION_PARAM,
        Value=json.dumps(session),
        Type="String",
        Overwrite=True,
    )

    all_ready = all(deploy_progress.get(svc, False) for svc in DEPLOY_PROGRESS_SERVICES)
    print("Action report-deploy-progress completed: 200")
    return 200, {
        "services": deploy_progress,
        "all_ready": all_ready,
    }


def handle_get_deploy_progress() -> tuple[int, dict[str, Any]]:
    """Get current deploy progress (no auth required)."""
    print("Action: get-deploy-progress")
    session = get_session()
    if session is None:
        print("Action get-deploy-progress completed: 200")
        return 200, {"services": {}, "all_ready": False}

    deploy_progress: dict[str, bool] = session.get("deploy_progress", {})
    if not deploy_progress:
        print("Action get-deploy-progress completed: 200")
        return 200, {"services": {}, "all_ready": False}

    all_ready = all(deploy_progress.get(svc, False) for svc in DEPLOY_PROGRESS_SERVICES)
    print("Action get-deploy-progress completed: 200")
    return 200, {"services": deploy_progress, "all_ready": all_ready}


def handle_set_teardown_run_id(api_key: str, run_id: int) -> tuple[int, dict[str, Any]]:
    """Store teardown workflow run ID in session.

    Called by teardown-platform.yml instead of writing SSM directly.
    """
    print("Action: set-teardown-run-id")
    if not validate_api_key(api_key):
        print("Action set-teardown-run-id completed: 401")
        return 401, {"error": "Invalid password"}

    session = get_session()
    if session is None:
        print("Action set-teardown-run-id completed: 404")
        return 404, {"error": "No active session"}

    session["teardown_run_id"] = run_id
    client = get_ssm_client()
    client.put_parameter(
        Name=SSM_SESSION_PARAM,
        Value=json.dumps(session),
        Type="String",
        Overwrite=True,
    )
    print("Action set-teardown-run-id completed: 200")
    return 200, {"success": True, "run_id": run_id}


def handle_complete_teardown(api_key: str) -> tuple[int, dict[str, Any]]:
    """Complete teardown by deleting the session.

    Called by teardown-platform.yml at the end instead of deleting SSM directly.
    """
    print("Action: complete-teardown")
    if not validate_api_key(api_key):
        print("Action complete-teardown completed: 401")
        return 401, {"error": "Invalid password"}

    session = get_session()
    if session is None:
        print("Action complete-teardown completed: 404")
        return 404, {"error": "No active session"}

    if not session.get("tearing_down", False):
        print("Action complete-teardown completed: 400")
        return 400, {"error": "Session is not in tearing_down state"}

    delete_session()
    print("Action complete-teardown completed: 200")
    return 200, {"success": True}


# ---------------------------------------------------------------------------
# Multi-service visitor provisioning
# ---------------------------------------------------------------------------

# Secret key used to retrieve the Grafana admin password for provisioning.
# The rideshare/monitoring secret is JSON-encoded and contains ADMIN_PASSWORD.
SECRET_GRAFANA_ADMIN_PASSWORD = "rideshare/monitoring"

# Secret key used to retrieve Airflow and MinIO credentials for provisioning.
# The rideshare/data-pipeline secret is JSON-encoded and contains
# ADMIN_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD among others.
SECRET_DATA_PIPELINE = "rideshare/data-pipeline"


def _hash_password_pbkdf2(password: str) -> str:
    """Hash a plaintext password with PBKDF2-SHA256 for Trino's file authenticator.

    Produces a hash string in the format accepted by Trino's ``password-file``
    authenticator (``password-authenticator.name=file``).  The output format is:

        ``{iterations}:{hex_salt}:{hex_hash}``

    where *iterations* is the PBKDF2 iteration count, *hex_salt* is the
    16-byte random salt encoded as lowercase hex, and *hex_hash* is the
    32-byte derived key encoded as lowercase hex.

    This is a pure-Python implementation using only standard-library modules
    (``hashlib``, ``os``), eliminating the native C dependency on a third-party
    hashing library that cannot be deployed in Lambda without platform-specific
    compilation.

    Args:
        password: Plaintext password to hash.

    Returns:
        Hash string suitable for direct insertion into Trino's ``password.db``
        file after the ``username:`` prefix.
    """
    import hashlib

    iterations = 65536
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{iterations}:{salt.hex()}:{digest.hex()}"


def _verify_password_pbkdf2(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a PBKDF2-SHA256 hash.

    The stored hash must be in the format produced by ``_hash_password_pbkdf2``:
    ``{iterations}:{hex_salt}:{hex_hash}``.

    Uses ``hmac.compare_digest`` for constant-time comparison to prevent
    timing attacks.

    Args:
        password: Plaintext password to verify.
        stored_hash: Hash string in ``iterations:hex_salt:hex_hash`` format.

    Returns:
        ``True`` if the password matches, ``False`` otherwise (including
        malformed hash strings).
    """
    import hashlib
    import hmac

    try:
        parts = stored_hash.split(":")
        if len(parts) != 3:
            return False
        iterations = int(parts[0])
        salt = bytes.fromhex(parts[1])
        expected_hash = bytes.fromhex(parts[2])
    except (ValueError, IndexError):
        return False

    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hmac.compare_digest(derived, expected_hash)


def _get_provisioning_scripts_dir() -> str:
    """Return the directory containing the provisioning module scripts.

    In the Lambda deployment package, the provisioning scripts are bundled
    alongside handler.py, so ``__file__``'s directory is used directly.  A
    ``PROVISIONING_SCRIPTS_DIR`` environment variable can override this for
    local development.

    Returns:
        Absolute path to the directory containing provision_*.py scripts.
    """
    override = os.environ.get("PROVISIONING_SCRIPTS_DIR")
    if override:
        return override
    # Co-located with handler.py inside the Lambda zip.
    return os.path.dirname(os.path.abspath(__file__))


def _load_module(module_name: str, scripts_dir: str) -> Any:
    """Load a provisioning module by file name from *scripts_dir*.

    Args:
        module_name: Base file name without extension, e.g.
            ``"provision_grafana_viewer"``.
        scripts_dir: Directory that contains the module file.

    Returns:
        The loaded module object.

    Raises:
        ImportError: If the module file cannot be found or loaded.
    """
    import importlib.util

    module_path = os.path.join(scripts_dir, f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _provision_grafana(
    email: str,
    password: str,
    name: str,
    scripts_dir: str,
) -> dict[str, Any]:
    """Provision a Grafana viewer account using environment-configured settings.

    Reads ``GRAFANA_URL`` and ``GRAFANA_ADMIN_PASSWORD`` (falling back to
    Secrets Manager for the password) from the environment.

    Args:
        email: Visitor email address.
        password: Visitor plaintext password.
        name: Visitor display name.
        scripts_dir: Directory containing provision_grafana_viewer.py.

    Returns:
        Result dict from :func:`provision_grafana_viewer.provision_viewer`.
    """
    grafana_url = os.environ.get("GRAFANA_URL", "http://localhost:3001")
    admin_password = os.environ.get("GRAFANA_ADMIN_PASSWORD")
    if not admin_password:
        try:
            secret_value = get_secret(SECRET_GRAFANA_ADMIN_PASSWORD)
            # rideshare/monitoring is a JSON-encoded secret containing
            # ADMIN_USER and ADMIN_PASSWORD fields.
            secret_data: dict[str, str] = json.loads(secret_value)
            admin_password = secret_data["ADMIN_PASSWORD"]
        except Exception:
            admin_password = "admin"

    credentials = base64.b64encode(f"admin:{admin_password}".encode()).decode()
    admin_auth_header = f"Basic {credentials}"

    module = _load_module("provision_grafana_viewer", scripts_dir)
    result: dict[str, Any] = module.provision_viewer(
        email=email,
        password=password,
        name=name,
        grafana_url=grafana_url,
        admin_auth_header=admin_auth_header,
    )

    lock_module = _load_module("lock_grafana_admin_folder", scripts_dir)
    lock_result: dict[str, Any] = lock_module.lock_admin_folder(
        grafana_url=grafana_url,
        admin_auth_header=admin_auth_header,
    )
    result["admin_folder"] = lock_result["status"]

    return result


def _provision_airflow(
    email: str,
    password: str,
    name: str,
    scripts_dir: str,
) -> dict[str, Any]:
    """Provision an Airflow viewer account using environment-configured settings.

    Reads ``AIRFLOW_URL``, ``AIRFLOW_ADMIN_USER``, and
    ``AIRFLOW_ADMIN_PASSWORD`` from the environment.

    Args:
        email: Visitor email address.
        password: Visitor plaintext password.
        name: Visitor display name.
        scripts_dir: Directory containing provision_airflow_viewer.py.

    Returns:
        Result dict from :func:`provision_airflow_viewer.provision_viewer`.
    """
    airflow_url = os.environ.get("AIRFLOW_URL", "http://localhost:8082")
    admin_user = os.environ.get("AIRFLOW_ADMIN_USER", "admin")
    admin_password = os.environ.get("AIRFLOW_ADMIN_PASSWORD")
    if not admin_password:
        try:
            secret_value = get_secret(SECRET_DATA_PIPELINE)
            secret_data: dict[str, str] = json.loads(secret_value)
            admin_password = secret_data["ADMIN_PASSWORD"]
        except Exception:
            admin_password = "admin"

    # Split display name into first / last for Airflow's user model.
    parts = name.strip().split(" ", 1)
    first_name = parts[0] if parts else email
    last_name = parts[1] if len(parts) > 1 else ""

    module = _load_module("provision_airflow_viewer", scripts_dir)
    result: dict[str, Any] = module.provision_viewer(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        airflow_url=airflow_url,
        admin_user=admin_user,
        admin_password=admin_password,
    )
    return result


def _provision_minio(
    email: str,
    password: str,
    scripts_dir: str,
) -> dict[str, Any]:
    """Provision a MinIO visitor account using environment-configured settings.

    Reads ``MINIO_ENDPOINT``, ``MINIO_ACCESS_KEY``, and ``MINIO_SECRET_KEY``
    from the environment.

    Args:
        email: Visitor email address (used as MinIO access key).
        password: Visitor plaintext password (used as MinIO secret key).
        scripts_dir: Directory containing provision_minio_visitor.py.

    Returns:
        Result dict from :func:`provision_minio_visitor.provision_visitor`.
    """
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY")
    secret_key = os.environ.get("MINIO_SECRET_KEY")
    if not access_key or not secret_key:
        try:
            secret_value = get_secret(SECRET_DATA_PIPELINE)
            secret_data_minio: dict[str, str] = json.loads(secret_value)
            access_key = access_key or secret_data_minio["MINIO_ROOT_USER"]
            secret_key = secret_key or secret_data_minio["MINIO_ROOT_PASSWORD"]
        except Exception:
            access_key = access_key or "admin"
            secret_key = secret_key or "adminadmin"

    module = _load_module("provision_minio_visitor", scripts_dir)
    result: dict[str, Any] = module.provision_visitor(
        email=email,
        password=password,
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
    )
    return result


def _provision_simulation_api(
    email: str,
    password: str,
    name: str,
    scripts_dir: str,
) -> dict[str, Any]:
    """Register the visitor in the simulation API user store.

    Delegates to the ``provision_simulation_api_viewer`` module loaded from
    *scripts_dir* via :func:`_load_module`.  The endpoint is idempotent —
    re-registering an existing email updates the password.

    Args:
        email: Visitor email address.
        password: Visitor plaintext password.
        name: Visitor display name (passed in the request body).
        scripts_dir: Directory containing ``provision_simulation_api_viewer.py``.

    Returns:
        The result dict from ``provision_viewer``, including a ``"status"``
        key (``"created"`` or ``"updated"``) and additional API response fields.
    """
    simulation_url = os.environ.get(
        "SIMULATION_API_URL",
        "https://api.ridesharing.portfolio.andresbrocco.com",
    )
    admin_api_key = get_secret(SECRET_API_KEY)

    module = _load_module("provision_simulation_api_viewer", scripts_dir)
    return module.provision_viewer(  # type: ignore[no-any-return]
        email=email,
        password=password,
        name=name,
        simulation_url=simulation_url,
        admin_api_key=admin_api_key,
    )


def _provision_visitor(
    email: str,
    password: str,
    name: str,
    durable_only: bool = False,
) -> dict[str, Any]:
    """Orchestrate visitor account creation across platform services.

    Calls each service's provisioning module in sequence.  Failures are
    caught, logged, and collected per-service rather than halting the whole
    operation — partial success is reported in the summary.

    When ``durable_only`` is True, no services are provisioned (previously
    Trino was provisioned in this mode, but it has been removed).

    Services provisioned (when ``durable_only=False``):
    - Grafana (viewer role)
    - Airflow (Viewer role)
    - MinIO (visitor-readonly policy)
    - Simulation API (viewer account in user store)

    Args:
        email: Visitor email address.
        password: Visitor plaintext password.
        name: Visitor display name.
        durable_only: When True, skip all service provisioning.

    Returns:
        Dict with ``"successes"`` and ``"failures"`` lists.  Each success
        entry is ``{"service": str, "result": dict}`` and each failure entry
        is ``{"service": str, "error": str}``.
    """
    scripts_dir = _get_provisioning_scripts_dir()
    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    if not durable_only:
        # Grafana
        try:
            result = _provision_grafana(email, password, name, scripts_dir)
            successes.append({"service": "grafana", "result": result})
            print(f"Grafana provisioning succeeded: {result}")
        except Exception as exc:
            failures.append({"service": "grafana", "error": str(exc)})
            print(f"Grafana provisioning failed: {exc}")

        # Airflow
        try:
            result = _provision_airflow(email, password, name, scripts_dir)
            successes.append({"service": "airflow", "result": result})
            print(f"Airflow provisioning succeeded: {result}")
        except Exception as exc:
            failures.append({"service": "airflow", "error": str(exc)})
            print(f"Airflow provisioning failed: {exc}")

        # MinIO (skip when endpoint not configured, e.g. production)
        minio_endpoint = os.environ.get("MINIO_ENDPOINT")
        if minio_endpoint:
            try:
                result = _provision_minio(email, password, scripts_dir)
                successes.append({"service": "minio", "result": result})
                print(f"MinIO provisioning succeeded: {result}")
            except Exception as exc:
                failures.append({"service": "minio", "error": str(exc)})
                print(f"MinIO provisioning failed: {exc}")
        else:
            print("MinIO provisioning skipped (MINIO_ENDPOINT not set)")

    if not durable_only:
        # Simulation API
        try:
            result = _provision_simulation_api(email, password, name, scripts_dir)
            successes.append({"service": "simulation_api", "result": result})
            print(f"Simulation API provisioning succeeded: {result}")
        except Exception as exc:
            failures.append({"service": "simulation_api", "error": str(exc)})
            print(f"Simulation API provisioning failed: {exc}")

    return {"successes": successes, "failures": failures}


def handle_provision_visitor(
    email: str,
    password: str | None,
    name: str,
) -> tuple[int, dict[str, Any]]:
    """Handle provision-visitor action (immediate provisioning).

    Provisions visitor accounts across all services — Grafana, Airflow,
    MinIO, and Simulation API — then stores the record in DynamoDB and
    sends a welcome email.

    When ``password`` is ``None`` or an empty string, a secure random password
    is generated automatically via :func:`secrets.token_urlsafe`.  Credentials
    are delivered exclusively via the SES welcome email — they are never
    included in the HTTP response body.  If the welcome email cannot be sent,
    the entire provisioning request fails with HTTP 500 so the visitor can
    retry rather than being left without credentials.

    Args:
        email: Visitor email address.
        password: Visitor plaintext password (min 8 characters), or ``None``
            to have one generated automatically.
        name: Visitor display name.

    Returns:
        Tuple of (HTTP status code, response body dict).  Status 200 when
        all services and email succeed; 207 when some services fail; 500 if
        all services fail or the welcome email fails.
    """
    print("Action: provision-visitor")

    if not email:
        print("Action provision-visitor completed: 400")
        return 400, {"error": "Missing required field: email"}

    if not name:
        name = email.split("@")[0]

    # Generate a password when the caller omits one; validate explicit passwords.
    if not password:
        effective_password = secrets.token_urlsafe(16)
    else:
        if len(password) < 8:
            print("Action provision-visitor completed: 400")
            return 400, {"error": "Password must be at least 8 characters"}
        effective_password = password

    consent_timestamp = datetime.now(timezone.utc).isoformat()

    result = _provision_visitor(email, effective_password, name, durable_only=False)
    successes = result["successes"]
    failures = result["failures"]

    try:
        _store_visitor_dynamodb(
            email, effective_password, [s["service"] for s in successes], consent_timestamp
        )
    except Exception as exc:
        print(f"DynamoDB visitor record storage failed (non-fatal): {exc}")

    all_failed = not successes and failures
    if all_failed:
        print("Action provision-visitor completed: 500")
        return 500, {
            "provisioned": False,
            "email_sent": False,
            "error": "All service provisioning failed",
            "failures": [f["service"] + ": " + f.get("error", "unknown") for f in failures],
        }

    email_sent = _send_welcome_email(email, name, effective_password)
    if not email_sent:
        print("Action provision-visitor completed: 500 (email delivery failed)")
        return 500, {
            "provisioned": True,
            "email_sent": False,
            "error": "Welcome email could not be delivered. Please retry.",
            "failures": [],
        }

    has_failures = bool(failures)
    status_code = 207 if has_failures else 200
    print(f"Action provision-visitor completed: {status_code}")
    return status_code, {
        "provisioned": True,
        "email_sent": True,
        "email": email,
        "failures": [f["service"] + ": " + f.get("error", "unknown") for f in failures],
    }


def handle_reprovision_visitors(api_key: str) -> tuple[int, dict[str, Any]]:
    """Re-provision all visitor accounts after platform redeploy.

    Scans the DynamoDB visitors table, decrypts each visitor's stored
    password, and calls :func:`_provision_visitor` to recreate ephemeral
    service accounts in Grafana, Airflow, MinIO, and the Simulation API.
    Requires admin API key authentication.

    The action is idempotent — all individual provisioners use create-or-
    update semantics, so re-running against a live platform is safe.

    Response codes:
    - 200: All visitors provisioned successfully (or table was empty).
    - 207: At least one visitor failed provisioning.
    - 401: Invalid API key.

    Args:
        api_key: Admin API key for authentication.

    Returns:
        Tuple of (HTTP status code, response body dict).
    """
    print("Action: reprovision-visitors")

    if not validate_api_key(api_key):
        print("Action reprovision-visitors completed: 401")
        return 401, {"error": "Invalid password"}

    table_name = os.environ.get("VISITOR_TABLE_NAME", "rideshare-visitors")
    dynamo = _get_dynamodb_client()

    visitors: list[dict[str, Any]] = []

    # Paginate through the full visitors table
    scan_kwargs: dict[str, Any] = {"TableName": table_name}
    while True:
        response = dynamo.scan(**scan_kwargs)
        visitors.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if last_key is None:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    if not visitors:
        print("Action reprovision-visitors completed: 200 (no visitors)")
        return 200, {"provisioned": 0, "failed": 0, "results": []}

    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for record in visitors:
        email_attr = record.get("email", {})
        email = email_attr.get("S", "") if isinstance(email_attr, dict) else str(email_attr)

        # name field may be absent on older records — fall back to email prefix
        name_attr = record.get("name", {})
        name = name_attr.get("S", email) if isinstance(name_attr, dict) else str(name_attr)
        if not name:
            name = email

        encrypted_password_attr = record.get("encrypted_password")
        if not encrypted_password_attr:
            reason = "no encrypted_password field — skipping"
            print(f"  Skipping {email}: {reason}")
            failures.append({"email": email, "error": reason})
            continue

        ciphertext_b64 = (
            encrypted_password_attr.get("S", "")
            if isinstance(encrypted_password_attr, dict)
            else str(encrypted_password_attr)
        )

        try:
            plaintext_password = _decrypt_password(ciphertext_b64)
        except Exception as dec_exc:
            reason = f"KMS decrypt failed: {dec_exc}"
            print(f"  Skipping {email}: {reason}")
            failures.append({"email": email, "error": reason})
            continue

        try:
            result = _provision_visitor(email, plaintext_password, name)
            visitor_failures = result.get("failures", [])
            if visitor_failures:
                failures.append(
                    {
                        "email": email,
                        "error": f"{len(visitor_failures)} service(s) failed",
                        "details": visitor_failures,
                    }
                )
            else:
                successes.append({"email": email, "services": result.get("successes", [])})
        except Exception as prov_exc:
            print(f"  Provisioning error for {email}: {prov_exc}")
            failures.append({"email": email, "error": str(prov_exc)})

    total = len(visitors)
    status_code = 207 if failures else 200
    print(
        f"Action reprovision-visitors completed: {status_code} "
        f"({len(successes)}/{total} succeeded)"
    )
    return status_code, {
        "provisioned": len(successes),
        "failed": len(failures),
        "results": successes,
        "failures": failures,
    }


def handle_start_simulation(
    api_key: str, agent_counts: dict[str, int] | None = None
) -> tuple[int, dict[str, Any]]:
    """Handle start-simulation action.

    Validates the caller, starts the simulation engine, then spawns agents
    according to the resolved counts (defaults merged with any overrides).

    Args:
        api_key: Caller's API key for authorization
        agent_counts: Optional overrides for any of the four agent count keys

    Returns:
        Tuple of (status_code, response_data)
    """
    print("Action: start-simulation")
    if not validate_api_key(api_key):
        print("Action start-simulation completed: 401")
        return 401, {"error": "Invalid API key"}

    counts = {**SIMULATION_START_DEFAULTS, **(agent_counts or {})}
    print(f"  Resolved agent counts: {counts}")

    admin_key = get_secret(SECRET_API_KEY)

    # Start the simulation engine
    sim_status, sim_body = _simulation_api_request("POST", "/simulation/start", admin_key, {})
    message = sim_body.get("message", "") if isinstance(sim_body, dict) else ""
    if sim_status == 200:
        simulation_started = True
        print("  Simulation started successfully")
    elif sim_status == 400 and "already running" in message.lower():
        simulation_started = True
        print("  Simulation already running — treating as success")
    else:
        simulation_started = False
        print(f"  Failed to start simulation: {sim_status} {sim_body}")

    # Spawn agent categories in order
    categories = [
        ("immediate_drivers", "driver", "immediate"),
        ("immediate_riders", "rider", "immediate"),
        ("scheduled_drivers", "driver", "scheduled"),
        ("scheduled_riders", "rider", "scheduled"),
    ]
    agents: dict[str, dict[str, Any]] = {}
    for category_key, agent_type, mode in categories:
        count = counts[category_key]
        endpoint = "drivers" if agent_type == "driver" else "riders"
        max_per_request = 100 if agent_type == "driver" else 2000
        total_queued = 0
        category_error: str | None = None

        remaining = count
        while remaining > 0:
            batch_size = min(remaining, max_per_request)
            batch_status, batch_body = _simulation_api_request(
                "POST",
                f"/agents/{endpoint}?mode={mode}",
                admin_key,
                {"count": batch_size},
            )
            if batch_status not in (200, 201, 202):
                batch_message = (
                    batch_body.get("message", str(batch_body))
                    if isinstance(batch_body, dict)
                    else str(batch_body)
                )
                category_error = f"HTTP {batch_status}: {batch_message}"
                print(f"  Error spawning {category_key}: {category_error}")
                break
            total_queued += batch_size
            remaining -= batch_size

        if category_error is not None:
            agents[category_key] = {
                "status": "error",
                "queued": total_queued,
                "error": category_error,
            }
        else:
            agents[category_key] = {"status": "ok", "queued": total_queued}
        print(f"  {category_key}: {agents[category_key]}")

    if not simulation_started:
        error_msg = f"HTTP {sim_status}: {message}" if message else f"HTTP {sim_status}"
        print("Action start-simulation completed: 502")
        return 502, {
            "simulation_started": False,
            "error": error_msg,
            "agents": agents,
            "success": False,
        }

    print("Action start-simulation completed: 200")
    return 200, {
        "simulation_started": True,
        "agents": agents,
        "success": True,
    }


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
            "get-deploy-progress": handle_get_deploy_progress,
            "extend-session": handle_extend_session,
            "shrink-session": handle_shrink_session,
        }
        auth_handlers: dict[str, Any] = {
            "validate": handle_validate,
            "deploy": handle_deploy,
            "status": handle_status,
            "activate-session": handle_activate_session,
            "ensure-session": handle_ensure_session,
            "complete-teardown": handle_complete_teardown,
            "reprovision-visitors": handle_reprovision_visitors,
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
        if action == "report-deploy-progress":
            service = event.get("service", "")
            ready = event.get("ready", True)
            _, response_body = handle_report_deploy_progress(api_key, service, ready)
            return response_body
        if action == "set-teardown-run-id":
            run_id = event.get("run_id")
            if run_id is None:
                return {"error": "Missing required field: run_id"}
            _, response_body = handle_set_teardown_run_id(api_key, run_id)
            return response_body
        if action == "provision-visitor":
            visitor_email = event.get("email", "")
            visitor_password = event.get("password") or None
            visitor_name = event.get("name", "")
            _, response_body = handle_provision_visitor(
                visitor_email, visitor_password, visitor_name
            )
            return response_body
        if action == "visitor-login":
            status_code, response_body = handle_visitor_login(
                event.get("email", ""), event.get("password", "")
            )
            return response_body
        if action == "start-simulation":
            agent_counts_override: dict[str, int] = {}
            for key in SIMULATION_START_DEFAULTS:
                val = event.get(key)
                if val is not None:
                    agent_counts_override[key] = int(val)
            _, response_body = handle_start_simulation(api_key, agent_counts_override or None)
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
                "get-deploy-progress",
                "activate-session",
                "ensure-session",
                "extend-session",
                "shrink-session",
                "report-deploy-progress",
                "set-teardown-run-id",
                "complete-teardown",
                "provision-visitor",
                "visitor-login",
                "reprovision-visitors",
                "start-simulation",
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
        "get-deploy-progress": handle_get_deploy_progress,
        "extend-session": handle_extend_session,
        "shrink-session": handle_shrink_session,
    }
    auth_handlers: dict[str, Any] = {
        "validate": handle_validate,
        "deploy": handle_deploy,
        "status": handle_status,
        "activate-session": handle_activate_session,
        "ensure-session": handle_ensure_session,
        "complete-teardown": handle_complete_teardown,
        "reprovision-visitors": handle_reprovision_visitors,
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
    elif action == "report-deploy-progress":
        service = body.get("service", "")
        ready = body.get("ready", True)
        status_code, response_body = handle_report_deploy_progress(api_key, service, ready)
    elif action == "set-teardown-run-id":
        run_id = body.get("run_id")
        if run_id is None:
            return {
                "statusCode": 400,
                "headers": response_headers,
                "body": json.dumps({"error": "Missing required field: run_id"}),
            }
        status_code, response_body = handle_set_teardown_run_id(api_key, run_id)
    elif action == "provision-visitor":
        visitor_email = body.get("email", "")
        visitor_password = body.get("password") or None
        visitor_name = body.get("name", "")
        status_code, response_body = handle_provision_visitor(
            visitor_email, visitor_password, visitor_name
        )
    elif action == "visitor-login":
        status_code, response_body = handle_visitor_login(
            body.get("email", ""), body.get("password", "")
        )
    elif action == "start-simulation":
        agent_counts_override: dict[str, int] = {}
        for key in SIMULATION_START_DEFAULTS:
            val = body.get(key)
            if val is not None:
                agent_counts_override[key] = int(val)
        status_code, response_body = handle_start_simulation(api_key, agent_counts_override or None)
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
                "get-deploy-progress",
                "activate-session",
                "ensure-session",
                "extend-session",
                "shrink-session",
                "report-deploy-progress",
                "set-teardown-run-id",
                "complete-teardown",
                "provision-visitor",
                "visitor-login",
                "reprovision-visitors",
                "start-simulation",
            ],
        }

    return {
        "statusCode": status_code,
        "headers": response_headers,
        "body": json.dumps(response_body),
    }
