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
GITHUB_WORKFLOW = "deploy.yml"
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
SESSION_STEP_MINUTES = 15
MAX_REMAINING_SECONDS = 2 * 3600  # 2 hours
PLATFORM_COST_PER_HOUR = 0.31
RESCHEDULE_DELAY_SECONDS = 300  # 5 min
TEARDOWN_TIMEOUT_SECONDS = 15 * 60  # 15 min — auto-clear stale tearing_down flag
DEPLOYING_TIMEOUT_SECONDS = 30 * 60  # 30 min — auto-clear stale deploying session

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
    "Grafana": {
        "url": "https://grafana.ridesharing.portfolio.andresbrocco.com",
        "desc": "Multi-datasource dashboards — metrics, logs, traces, and BI analytics",
    },
    "Airflow": {
        "url": "https://airflow.ridesharing.portfolio.andresbrocco.com",
        "desc": "4 DAGs orchestrating Bronze → Silver → Gold transformations",
    },
    "Trino": {
        "url": "https://trino.ridesharing.portfolio.andresbrocco.com/ui",
        "desc": "Interactive SQL over Delta Lake — query the star schema live",
    },
    "MinIO": {
        "url": "https://minio.ridesharing.portfolio.andresbrocco.com",
        "desc": "S3-compatible object storage — browse the raw lakehouse files",
    },
    "Simulation API": {
        "url": "https://api.ridesharing.portfolio.andresbrocco.com/docs",
        "desc": "FastAPI Swagger docs — start sessions, spawn agents, control speed",
    },
}

SERVICE_LOGIN_URLS: dict[str, str] = {name: info["url"] for name, info in SERVICE_INFO.items()}

LANDING_PAGE_URL = "https://ridesharing.portfolio.andresbrocco.com"
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
        f"Note: These credentials activate once the platform is deployed. "
        f'After clicking "Deploy" on the landing page, services typically start '
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

    # Inline SVG icons (Simple Icons paths, same brands as landing page)
    def _svg_icon(path: str, color: str) -> str:
        return (
            f'<img src="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27'
            f" viewBox=%270 0 24 24%27%3E%3Cpath fill=%27{color.replace('#', '%23')}%27"
            f' d=%27{path}%27/%3E%3C/svg%3E"'
            f' width="18" height="18" alt=""'
            f' style="vertical-align:middle;margin-right:8px;">'
        )

    service_icons: dict[str, str] = {
        "Control Panel": _svg_icon(
            "M14.23 12.004a2.236 2.236 0 0 1-2.235 2.236 2.236 2.236 0 0 1-2.236-2.236"
            " 2.236 2.236 0 0 1 2.235-2.236 2.236 2.236 0 0 1 2.236 2.236zm2.648-10.69c-1.346"
            " 0-3.107.96-4.888 2.622-1.78-1.653-3.542-2.602-4.887-2.602-.41"
            " 0-.783.093-1.106.278-1.375.793-1.683 3.264-.973 6.365C1.98 8.917 0 10.42 0"
            " 12.004c0 1.59 1.99 3.097 5.043 4.03-.704 3.113-.39 5.588.988 6.38.32.187.69.275"
            " 1.102.275 1.345 0 3.107-.96 4.888-2.624 1.78 1.654 3.542 2.603 4.887 2.603.41"
            " 0 .783-.09 1.106-.275 1.374-.792 1.683-3.263.973-6.365C22.02 15.096 24 13.59 24"
            " 12.004c0-1.59-1.99-3.097-5.043-4.032.704-3.11.39-5.587-.988-6.38-.318-.184-.688"
            "-.277-1.092-.278zm-.005 1.09v.006c.225 0 .406.044.558.127.666.382.955 1.835.73"
            " 3.704-.054.46-.142.945-.25 1.44-.96-.236-2.006-.417-3.107-.534-.66-.905-1.345"
            "-1.727-2.035-2.447 1.592-1.48 3.087-2.292 4.105-2.295zm-9.77.02c1.012 0 2.514.808"
            " 4.11 2.28-.686.72-1.37 1.537-2.02 2.442-1.107.117-2.154.298-3.113.538-.112-.49"
            "-.195-.964-.254-1.42-.23-1.868.054-3.32.714-3.707.19-.09.4-.127.563-.132zm4.882"
            " 3.05c.455.468.91.992 1.36 1.564-.44-.02-.89-.034-1.345-.034-.46"
            " 0-.915.01-1.36.034.44-.572.895-1.096 1.345-1.565zM12 8.1c.74 0"
            " 1.477.034 2.202.093.406.582.802 1.203 1.183 1.86.372.64.71 1.29 1.018"
            " 1.946-.308.655-.646 1.31-1.013 1.95-.38.66-.773 1.288-1.18 1.87-.728.063-1.466"
            ".098-2.21.098-.74 0-1.477-.035-2.202-.093-.406-.582-.802-1.204-1.183-1.86-.372"
            "-.64-.71-1.29-1.018-1.946.303-.657.646-1.313 1.013-1.954.38-.66.773-1.286 1.18"
            "-1.868.728-.064 1.466-.098 2.21-.098zm-3.635.254c-.24.377-.48.763-.704"
            " 1.16-.225.39-.435.782-.635 1.174-.265-.656-.49-1.31-.676-1.947.64-.15 1.315-.283"
            " 2.015-.386zm7.26 0c.695.103 1.365.23 2.006.387-.18.632-.405 1.282-.66"
            " 1.933-.2-.39-.41-.783-.64-1.174-.225-.392-.465-.774-.705-1.146zm3.063.675c.484.15"
            ".944.317 1.375.498 1.732.74 2.852 1.708 2.852 2.476-.005.768-1.125 1.74-2.857"
            " 2.475-.42.18-.88.342-1.355.493-.28-.958-.646-1.956-1.1-2.98.45-1.017.81-2.01"
            " 1.085-2.964zm-13.395.004c.278.96.645 1.957 1.1 2.98-.45 1.017-.812 2.01-1.086"
            " 2.964-.484-.15-.944-.318-1.37-.5-1.732-.737-2.852-1.706-2.852-2.474"
            " 0-.768 1.12-1.742 2.852-2.476.42-.18.88-.342 1.356-.494zm11.678"
            " 4.28c.265.657.49 1.312.676 1.948-.64.157-1.316.29-2.016.39.24-.375.48-.762.705"
            "-1.158.225-.39.435-.788.636-1.18zm-9.945.02c.2.392.41.783.64"
            " 1.175.23.39.465.772.705 1.143-.695-.102-1.365-.23-2.006-.386.18-.63.406-1.282.66"
            "-1.933zM17.92 16.32c.112.493.2.968.254 1.423.23 1.868-.054 3.32-.714"
            " 3.708-.147.09-.338.128-.563.128-1.012 0-2.514-.807-4.11-2.28.686-.72 1.37-1.536"
            " 2.02-2.44 1.107-.118 2.154-.3 3.113-.54zm-11.83.01c.96.234 2.006.415"
            " 3.107.532.66.905 1.345 1.727 2.035 2.446-1.595 1.483-3.092 2.295-4.11"
            " 2.295-.22-.005-.406-.05-.553-.132-.666-.38-.955-1.834-.73-3.703.054-.46.142-.944"
            ".25-1.438zm4.56.64c.44.02.89.034 1.345.034.46 0 .915-.01 1.36-.034-.44.572-.895"
            " 1.095-1.345 1.565-.455-.47-.91-.993-1.36-1.565z",
            "#61DAFB",
        ),
        "Grafana": _svg_icon(
            "M23.02 10.59a8.578 8.578 0 0 0-.862-3.034 8.911 8.911 0 0 0-1.789-2.445c.337"
            "-1.342-.413-2.505-.413-2.505-1.292-.08-2.113.4-2.416.62-.052-.02-.102-.044-.154"
            "-.064-.22-.089-.446-.172-.677-.247-.231-.073-.47-.14-.711-.197a9.867 9.867 0 0"
            " 0-.875-.161C14.557.753 12.94 0 12.94 0c-1.804 1.145-2.147 2.744-2.147"
            " 2.744l-.018.093c-.098.029-.2.057-.298.088-.138.042-.275.094-.413.143-.138.055"
            "-.275.107-.41.166a8.869 8.869 0 0 0-1.557.87l-.063-.029c-2.497-.955-4.716.195"
            "-4.716.195-.203 2.658.996 4.33 1.235 4.636a11.608 11.608 0 0 0-.607 2.635C1.636"
            " 12.677.953 15.014.953 15.014c1.926 2.214 4.171 2.351 4.171"
            " 2.351.003-.002.006-.002.006-.005.285.509.615.994.986"
            " 1.446.156.19.32.371.488.548-.704 2.009.099 3.68.099 3.68 2.144.08 3.553-.937"
            " 3.849-1.173a9.784 9.784 0 0 0 3.164.501h.08l.055-.003.107-.002.103-.005.003.002c"
            "1.01 1.44 2.788 1.646 2.788 1.646 1.264-1.332 1.337-2.653"
            " 1.337-2.94v-.058c0-.02-.003-.039-.003-.06.265-.187.52-.387.758-.6a7.875 7.875 0"
            " 0 0 1.415-1.7c1.43.083 2.437-.885 2.437-.885-.236-1.49-1.085-2.216-1.264"
            "-2.354l-.018-.013-.016-.013a.217.217 0 0 1-.031-.02c.008-.092.016-.18.02-.27.011"
            "-.162.016-.323.016-.48v-.253l-.005-.098-.008-.135a1.891 1.891 0 0 0-.01-.13c-.003"
            "-.042-.008-.083-.013-.125l-.016-.124-.018-.122a6.215 6.215 0 0 0-2.032-3.73 6.015"
            " 6.015 0 0 0-3.222-1.46 6.292 6.292 0 0 0-.85-.048l-.107.002h-.063l-.044.003-.104"
            ".008a4.777 4.777 0 0 0-3.335 1.695c-.332.4-.592.84-.768 1.297a4.594 4.594 0 0"
            " 0-.312 1.817l.003.091c.005.055.007.11.013.164a3.615 3.615 0 0 0 .698 1.82 3.53"
            " 3.53 0 0 0 1.827 1.282c.33.098.66.14.971.137.039 0 .078 0 .114-.002l.063-.003c"
            ".02 0 .041-.003.062-.003.034-.002.065-.007.099-.01.007 0 .018-.003.028-.003l.031"
            "-.005.06-.008a1.18 1.18 0 0 0 .112-.02c.036-.008.072-.013.109-.024a2.634 2.634 0"
            " 0 0 .914-.415c.028-.02.056-.041.085-.065a.248.248 0 0 0 .039-.35.244.244 0 0"
            " 0-.309-.06l-.078.042c-.09.044-.184.083-.283.116a2.476 2.476 0 0"
            " 1-.475.096c-.028.003-.054.006-.083.006l-.083.002c-.026"
            " 0-.054 0-.08-.002l-.102-.006h-.012l-.024.006c-.016-.003-.031-.003-.044-.006-.031"
            "-.002-.06-.007-.091-.01a2.59 2.59 0 0 1-.724-.213 2.557 2.557 0 0 1-.667-.438"
            " 2.52 2.52 0 0 1-.805-1.475 2.306 2.306 0 0 1-.029-.444l.006-.122v-.023l.002"
            "-.031c.003-.021.003-.04.005-.06a3.163 3.163 0 0 1 1.352-2.29 3.12 3.12 0 0 1"
            " .937-.43 2.946 2.946 0 0 1 .776-.101h.06l.07.002.045.003h.026l.07.005a4.041"
            " 4.041 0 0 1 1.635.49 3.94 3.94 0 0 1 1.602 1.662 3.77 3.77 0 0 1 .397"
            " 1.414l.005.076.003.075c.002.026.002.05.002.075 0 .024.003.052"
            " 0 .07v.065l-.002.073-.008.174a6.195 6.195 0 0 1-.08.639 5.1 5.1 0 0 1-.267.927"
            " 5.31 5.31 0 0 1-.624 1.13 5.052 5.052 0 0 1-3.237 2.014 4.82 4.82 0 0 1-.649"
            ".066l-.039.003h-.287a6.607 6.607 0 0 1-1.716-.265 6.776 6.776 0 0 1-3.4-2.274"
            " 6.75 6.75 0 0 1-.746-1.15 6.616 6.616 0 0 1-.714-2.596l-.005-.083-.002-.02v"
            "-.056l-.003-.073v-.096l-.003-.104v-.07l.003-.163c.008-.22.026-.45.054-.678a8.707"
            " 8.707 0 0 1 .28-1.355c.128-.444.286-.872.473-1.277a7.04 7.04 0 0 1 1.456-2.1"
            " 5.925 5.925 0 0 1 .953-.763c.169-.111.343-.213.524-.306.089-.05.182-.091.273"
            "-.135.047-.02.093-.042.138-.062a7.177 7.177 0 0 1 .714-.267l.145-.045c.049-.015"
            ".098-.026.148-.041.098-.029.197-.052.296-.076.049-.013.1-.02.15-.033l.15-.032.151"
            "-.028.076-.013.075-.01.153-.024c.057-.01.114-.013.171-.023l.169-.021c.036-.003.073"
            "-.008.106-.01l.073-.008.036-.003.042-.002c.057-.003.114-.008.171-.01l.086-.006h"
            ".023l.037-.003.145-.007a7.999 7.999 0 0 1 1.708.125 7.917 7.917 0 0 1 2.048.68"
            " 8.253 8.253 0 0 1 1.672 1.09l.09.077.089.078c.06.052.114.107.171.159.057.052.112"
            ".106.166.16.052.055.107.107.159.164a8.671 8.671 0 0 1 1.41 1.978c.012.026.028.052"
            ".04.078l.04.078.075.156c.023.051.05.1.07.153l.065.15a8.848 8.848 0 0 1 .45"
            " 1.34.19.19 0 0 0 .201.142.186.186 0 0 0 .172-.184c.01-.246.002-.532-.024-.856z",
            "#F46800",
        ),
        "Airflow": _svg_icon(
            "M17.195 16.822l4.002-4.102C23.55 10.308 23.934 5.154 24 .43a.396.396 0 0"
            " 0-.246-.373.392.392 0 0 0-.437.09l-6.495 6.658-4.102-4.003C10.309.45 5.154.066.43"
            " 0H.423a.397.397 0 0 0-.277.683l6.658 6.494-4.003 4.103C.45 13.692.065 18.846 0"
            " 23.57a.398.398 0 0 0 .683.282l6.494-6.657 3.934 3.837.17.165c2.41 2.353 7.565"
            " 2.737 12.288 2.803h.006a.397.397 0 0 0 .277-.683l-6.657-6.495zm-.409-9.476c.04"
            ".115.05.24.031.344-.17.96-1.593 2.538-4.304 3.87a.597.597 0 0 0-.08-.079c1.432"
            "-3.155 1.828-5.61 1.175-7.322l3.058 2.984.12.203zm-.131 9.44a.73.73 0 0 1-.347"
            ".031c-.96-.171-2.537-1.594-3.87-4.307a.656.656 0 0 0 .08-.078l-.001.001c3.155"
            " 1.432 5.61 1.83 7.324 1.174l-2.969 3.043M23.568.392a.05.05 0 0 1 .052-.011c.018"
            ".006.03.024.029.043-.065 4.655-.437 9.726-2.703 12.05-1.53 1.565-4.326 1.419-8.283"
            "-.377.006-.037.021-.07.02-.108 0-.044-.017-.082-.026-.123 2.83-1.39 4.315-3.037"
            " 4.506-4.115.057-.322-.009-.542-.102-.688l6.507-6.67V.392zM.393.43A.045.045 0 0"
            " 1 .382.38C.39.36.403.343.425.35c4.655.065 9.727.438 12.05 2.703l.002.002c1.56"
            " 1.527 1.415 4.323-.379 8.28-.033-.005-.062-.02-.097-.02h-.008c-.045.001-.084.019"
            "-.126.027-1.39-2.83-3.037-4.314-4.115-4.506-.323-.057-.542.01-.688.103L.393.43zm"
            "11.94 11.563a.331.331 0 0 1-.327.335H12a.332.332 0 0 1-.004-.661c.172.016.333.144"
            ".335.326h.002zm-5.12 4.661a.722.722 0 0 1-.03-.345c.17-.96 1.595-2.54 4.309-3.873"
            ".013.016.019.035.033.05.013.012.03.017.044.028-1.434 3.158-1.83 5.613-1.177"
            " 7.326l-3.041-2.967m-.006-9.659a.735.735 0 0 1 .345-.031c.961.17 2.54 1.594 3.871"
            " 4.306a.597.597 0 0 0-.079.08c-2.167-.983-4.007-1.484-5.498-1.484-.68 0-1.289.103"
            "-1.825.308L7.128 7.35M.43 23.607c-.018.018-.038.015-.052.01-.019-.007-.028-.021"
            "-.028-.043.065-4.654.437-9.725 2.703-12.049 1.527-1.565 4.325-1.419 8.286.378"
            "-.006.035-.02.067-.02.104 0 .043.018.083.026.124-2.831 1.391-4.317 3.04-4.51"
            " 4.117-.057.322.01.542.103.688L.43 23.607zm23.144.042c-4.655-.065-9.726-.437"
            "-12.05-2.703l-.005-.006c-1.56-1.526-1.412-4.322.383-8.279.033.005.064.02.098.02h"
            ".009c.043 0 .08-.018.122-.027 1.39 2.832 3.036 4.317 4.115 4.51.083.014.16.021.23"
            ".021a.776.776 0 0 0 .45-.133l6.68 6.516c.02.02.016.04.01.052a.042.042 0 0 1-.042"
            ".029z",
            "#2098FF",
        ),
        "Trino": _svg_icon(
            "M13.2072.006c-.6216-.0478-1.2.1943-1.6211.582a2.15 2.15 0 0 0-.0938 3.0352l3.4082"
            " 3.5507a3.042 3.042 0 0 1-.664 4.6875l-.463.2383V7.2853a15.4198 15.4198 0 0"
            " 0-8.0174 10.4862v.0176l6.5487-3.3281v7.621L13.7794 24V13.6817l.8965-.4629a4.4432"
            " 4.4432 0 0 0 1.2207-7.0292l-3.371-3.5254a.7489.7489 0 0 1 .037-1.0547.7522.7522"
            " 0 0 1 1.0567.0371l.4668.4863-.006.0059 4.0704 4.2441a.0566.0566 0 0 0 .082"
            " 0 .06.06 0 0 0 0-.0703l-3.1406-5.1425-.1484.1425.1484-.1445C14.4945.3926"
            " 13.8287.0538 13.2072.006Zm-.9024 9.8652v2.9941l-4.1523 2.1484a13.9787 13.9787 0"
            " 0 1 2.7676-3.9277 14.1784 14.1784 0 0 1 1.3847-1.2148z",
            "#F020B8",
        ),
        "MinIO": _svg_icon(
            "M12 .0387C5.3729.0384.0003 5.3931 0 11.9988c-.001 6.6066 5.372 11.9628 12"
            " 11.9625 6.628.0003 12.001-5.3559 12-11.9625-.0003-6.6057-5.3729-11.9604-12"
            "-11.96m-.829 5.4153h7.55l-7.5805 5.3284h5.1828L5.279 18.5436q2.9466-6.5444"
            " 5.892-13.0896",
            "#E8506E",
        ),
        "Simulation API": _svg_icon(
            "M12 0C5.375 0 0 5.375 0 12c0 6.627 5.375 12 12 12 6.626 0 12-5.373 12-12"
            " 0-6.625-5.373-12-12-12zm-.624 21.62v-7.528H7.19L13.203 2.38v7.528h4.029L11.376"
            " 21.62z",
            "#009688",
        ),
    }

    # Car favicon icon for landing page link (same as control-panel favicon, 24x24)
    car_icon = (
        '<img src="data:image/png;base64,'
        "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAAAXNSR0IArs4c6QAAAERlWElmTU0AKgAA"
        "AAgAAYdpAAQAAAABAAAAGgAAAAAAA6ABAAMAAAABAAEAAKACAAQAAAABAAAAGKADAAQAAAABAAAAGAAAAA"
        "DiNXWtAAACgElEQVRIDe2Uz4uNURjHv+fOHfeOUiOzMYRiYUHyKxRiaSlCdlY2SokuG43FcEdK+QOG"
        "jc2E8BdMUhg/Sk2xsLFgJSly3XfufY/Pc8774xIxNRZqnjrnfZ73+T6/zznSPP2/HfDNffKjS/9U"
        "gCsA/tIaqXpA8gulLv9dP7oFhf4HxnfRH2Y9Af+qVLkU/qXUui83YrxiAH91UGo/kuprMcjw7bvwD"
        "6QKQXyZiJQAWM46TnyS6SWDdb6wbuDvpAWpRnWyWerD+TcT2/A11lYpvSnXuBUx2e4vgquOExjnCV"
        "jXk4C5SxvojkoDWxCmsgB+HQ6RQwbnadFGqXYEBxPyzUn+t1BCoZLtUv9i8ngD7gR2FmwYx+jN3r9"
        "lPYTfhpAH0EoEyEB+CuNrMBhVd/PdGw3hAhkm+YDj/XJnp0mAOcAHW9NpD3ZLCG4zVMU2nA7Fb8r"
        "w0k/0znr1Iqo7sDM9KyDfy52ZDpzc8zIBzNV3mgqPwVBlEcANmAAQb+5r5H3Wvij9tFfkJ6ynUPqO"
        "BCMbdgtiS4tsyyow9t9Q3qJ8iGRt98DIqvktpXKHQprkuKxskeGtsFDcZ5OyAI6hBRFNZVB+pI60KQ"
        "7OOmXzypfh3DDDXW8cCXHE8xaZ4+4VZnYdzEfT5n3maBlZvC7Hq84lqnGCEiz9JOC8QgeAY1rjULT"
        "vEIRjKvBZMdEefGcXNsymCOA4EQay5S7wm4vWAZByG8/dNmBB4aLNjIPZAeYeeC5aOJ5AQiWrSHQn"
        "wimzySpocdTqr7OnAudG7adsK+THGhha5jnxVKSPWRt+/VT4ZvZUPDOD0tBfXo14EGcMee4euzyr2X"
        '//8rmeveN5i7nuwHfs8scFjQp7TgAAAABJRU5ErkJggg=="'
        ' width="16" height="16" alt=""'
        ' style="vertical-align:middle;margin-right:4px;">'
    )

    service_rows_html = ""
    for svc, info in SERVICE_INFO.items():
        icon = service_icons.get(svc, "")
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
        f"<strong>Note:</strong> These credentials activate once the platform is deployed. "
        f'After clicking "Deploy" on the landing page, services typically start '
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
        print("Action deploy completed: 409")
        return 409, {"error": "Deployment already in progress"}

    try:
        github_pat = get_secret(SECRET_GITHUB_PAT)
    except Exception as e:
        print(f"Error retrieving GitHub PAT: {e}")
        print("Action deploy completed: 500")
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
        print("Action session-status completed: 200")
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
                    if latest_status not in ("in_progress", "queued"):
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
            delete_session()
            print("Action session-status completed: 200")
            return 200, {"active": False}

        # GitHub API validation: if deploy workflow failed/cancelled, clean up.
        # A successful completion is expected — the frontend will call
        # activate-session once deploy-progress reports all_ready.
        try:
            github_pat = get_secret(SECRET_GITHUB_PAT)
            path = f"/repos/{GITHUB_REPO}/actions/workflows/" f"{GITHUB_WORKFLOW}/runs?per_page=1"
            gh_status, gh_data = github_api_request("GET", path, github_pat)
            if gh_status == 200:
                runs = gh_data.get("workflow_runs", [])
                if runs:
                    conclusion = runs[0].get("conclusion", "")
                    if conclusion in ("failure", "cancelled"):
                        delete_session()
                        print("Action session-status completed: 200")
                        return 200, {"active": False}
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

    # Case 3: Session with deadline already set — idempotent
    if session is not None and session.get("deadline") is not None:
        remaining = max(0, session["deadline"] - now)
        print("Action ensure-session completed: 200 (already activated)")
        return 200, {
            "success": True,
            "remaining_seconds": remaining,
            "deadline": session["deadline"],
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

# Secrets Manager key where the Trino PBKDF2 password hash is persisted so
# that a Trino container restart can pick it up via the password.db entrypoint script.
SECRET_TRINO_VISITOR_PASSWORD_HASH = "rideshare/trino-visitor-password-hash"

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


def _provision_trino(email: str, password: str) -> dict[str, Any]:
    """Hash the visitor password with PBKDF2-SHA256 and store it in Secrets Manager.

    Trino reads the hashed password from Secrets Manager during container
    start-up via the entrypoint script that regenerates ``password.db``.
    The container must be manually restarted after this call for the new
    credentials to take effect.

    Args:
        email: Visitor email address (stored alongside the hash for reference).
        password: Visitor plaintext password to hash.

    Returns:
        Dict with ``"status": "stored"`` and ``"email"`` on success.
    """
    hashed = _hash_password_pbkdf2(password)

    # Persist the hash so the Trino container can pick it up on restart.
    client = get_secrets_client()
    secret_value = json.dumps({"email": email, "hash": hashed})
    try:
        client.put_secret_value(
            SecretId=SECRET_TRINO_VISITOR_PASSWORD_HASH,
            SecretString=secret_value,
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            client.create_secret(
                Name=SECRET_TRINO_VISITOR_PASSWORD_HASH,
                SecretString=secret_value,
            )
        else:
            raise

    return {"status": "stored", "email": email}


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

    When ``durable_only`` is True, only Trino provisioning (Secrets Manager
    storage) is attempted — the remaining services require a running platform
    and are skipped.  This mode is used by ``handle_provision_visitor`` for
    pre-deploy credential storage.  The full set of services is provisioned
    when ``durable_only`` is False, which is used by
    ``handle_reprovision_visitors`` after the platform is deployed.

    Services provisioned (when ``durable_only=False``):
    - Grafana (viewer role)
    - Airflow (Viewer role)
    - MinIO (visitor-readonly policy)
    - Trino (PBKDF2 hash stored in Secrets Manager; restart required)
    - Simulation API (viewer account in user store)

    Args:
        email: Visitor email address.
        password: Visitor plaintext password.
        name: Visitor display name.
        durable_only: When True, only provision services that write to
            durable storage (Secrets Manager) and skip those requiring a
            running platform.

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

    # Trino (stores PBKDF2 hash; manual container restart required)
    try:
        result = _provision_trino(email, password)
        successes.append({"service": "trino", "result": result})
        print(f"Trino provisioning succeeded: {result}")
    except Exception as exc:
        failures.append({"service": "trino", "error": str(exc)})
        print(f"Trino provisioning failed: {exc}")

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
    """Handle provision-visitor action (Phase 1: durable-only).

    Stores visitor credentials durably (Trino hash in Secrets Manager,
    record in DynamoDB) and sends a welcome email.  Service accounts in
    Grafana, Airflow, MinIO, and the Simulation API are **not** created
    here — they require a running platform and are provisioned later by
    ``handle_reprovision_visitors`` (Phase 2, called from the deploy
    workflow).

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
        credential storage and email succeed; 500 if storage fails or
        the welcome email fails.
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

    result = _provision_visitor(email, effective_password, name, durable_only=True)
    successes = result["successes"]
    failures = result["failures"]

    try:
        _store_visitor_dynamodb(
            email, effective_password, ["trino"] if successes else [], consent_timestamp
        )
    except Exception as exc:
        print(f"DynamoDB visitor record storage failed (non-fatal): {exc}")

    if not successes:
        print("Action provision-visitor completed: 500")
        return 500, {
            "provisioned": False,
            "email_sent": False,
            "error": "Credential storage failed",
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
    service accounts in Grafana, Airflow, MinIO, Trino, and the Simulation
    API.  Requires admin API key authentication.

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
            ],
        }

    return {
        "statusCode": status_code,
        "headers": response_headers,
        "body": json.dumps(response_body),
    }
