#!/usr/bin/env python3
"""CLI wrapper for the multi-service visitor provisioning orchestrator.

Provisions a visitor account across all platform services — Grafana, Airflow,
MinIO, and the Simulation API — using the same logic that runs in the
Lambda ``provision-visitor`` action.

Service URLs and admin credentials are read from environment variables so that
this script works identically against local Docker Compose and production EKS.

Usage examples:

    # Local Docker Compose (defaults apply when env vars are not set):
    ./venv/bin/python3 infrastructure/scripts/provision_visitor_cli.py \\
        --email visitor@example.com \\
        --password "Str0ngP@ssword!" \\
        --name "Jane Visitor"

    # Production (set env vars before running):
    GRAFANA_URL=https://grafana.example.com \\
    AIRFLOW_URL=https://airflow.example.com \\
    MINIO_ENDPOINT=s3.example.com \\
    SIMULATION_API_URL=https://api.example.com \\
    ./venv/bin/python3 infrastructure/scripts/provision_visitor_cli.py \\
        --email visitor@example.com \\
        --password "Str0ngP@ssword!" \\
        --name "Jane Visitor"

Environment variables (all optional — defaults target local Docker Compose):

    GRAFANA_URL             Base Grafana URL            (default: http://localhost:3001)
    GRAFANA_ADMIN_PASSWORD  Grafana admin password      (default: admin)
    AIRFLOW_URL             Base Airflow URL            (default: http://localhost:8082)
    AIRFLOW_ADMIN_USER      Airflow admin username      (default: admin)
    AIRFLOW_ADMIN_PASSWORD  Airflow admin password      (default: admin)
    MINIO_ENDPOINT          MinIO host:port             (default: localhost:9000)
    MINIO_ACCESS_KEY        MinIO admin access key      (default: admin)
    MINIO_SECRET_KEY        MinIO admin secret key      (default: adminadmin)
    SIMULATION_API_URL      Simulation API base URL     (default: http://localhost:8000)
    SIMULATION_API_KEY      Admin API key               (default: admin)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make the provisioning modules importable without installing them
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS_DIR = Path(__file__).parent

# Set PROVISIONING_SCRIPTS_DIR so the orchestrator helpers in handler.py can
# locate the provisioning modules when called from this CLI.
os.environ.setdefault("PROVISIONING_SCRIPTS_DIR", str(_SCRIPTS_DIR))

# handler.py lives inside the Lambda package directory.
sys.path.insert(0, str(_REPO_ROOT / "services" / "auth-deploy"))

# The provisioning modules themselves live in the same directory as this script.
sys.path.insert(0, str(_SCRIPTS_DIR))

# LocalStack endpoint for Secrets Manager (used by handler.get_secrets_client).
os.environ.setdefault("LOCALSTACK_HOSTNAME", "localhost")

# ---------------------------------------------------------------------------
# Late import — must come after sys.path setup
# ---------------------------------------------------------------------------

from handler import _provision_visitor  # noqa: E402  (after sys.path mutation)


# ---------------------------------------------------------------------------
# Local-dev credential helpers
# ---------------------------------------------------------------------------

# These defaults match the Docker Compose service configuration.  They are
# applied as environment variable defaults so the provisioning helpers in
# handler.py pick them up without modification.
_LOCAL_DEFAULTS: dict[str, str] = {
    "GRAFANA_URL": "http://localhost:3001",
    "GRAFANA_ADMIN_PASSWORD": "admin",
    "AIRFLOW_URL": "http://localhost:8082",
    "AIRFLOW_ADMIN_USER": "admin",
    "AIRFLOW_ADMIN_PASSWORD": "admin",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "admin",
    "MINIO_SECRET_KEY": "adminadmin",
    "SIMULATION_API_URL": "http://localhost:8000",
}

# The simulation API key is handled separately because handler._provision_simulation_api
# reads it via get_secret(), which in local dev needs a working LocalStack.  Allow an
# override so this CLI can be used with a plain env var instead.
_SIMULATION_API_KEY_ENV = "SIMULATION_API_KEY"


def _apply_local_defaults() -> None:
    """Apply default Docker Compose service URLs and credentials.

    Only sets variables that are not already present in the environment,
    so explicit overrides always take precedence.
    """
    for key, value in _LOCAL_DEFAULTS.items():
        os.environ.setdefault(key, value)


def _patch_get_secret_for_local_dev() -> None:
    """Override handler.get_secret to read the admin key from the environment.

    In local development the Lambda's Secrets Manager client talks to
    LocalStack.  If LocalStack is not running, the call fails.  When
    SIMULATION_API_KEY is set in the environment, skip Secrets Manager
    entirely.
    """
    import handler as _handler

    api_key_from_env = os.environ.get(_SIMULATION_API_KEY_ENV)
    if not api_key_from_env:
        return  # Let the real Secrets Manager path run (LocalStack must be up)

    _original_get_secret = _handler.get_secret

    def patched_get_secret(secret_id: str) -> str:
        if secret_id == _handler.SECRET_API_KEY:
            return api_key_from_env
        return _original_get_secret(secret_id)

    _handler.get_secret = patched_get_secret  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="Provision a visitor account across all platform services.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Visitor email address (used as login for all services).",
    )
    parser.add_argument(
        "--password",
        required=True,
        help="Visitor plaintext password (min 8 characters).",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Visitor display name shown in service UIs.",
    )
    return parser


def main() -> int:
    """Parse arguments, provision the visitor, and print a summary.

    Returns:
        Exit code: 0 if at least one service succeeded, 1 if all failed.
    """
    parser = build_parser()
    args = parser.parse_args()

    if len(args.password) < 8:
        print("Error: password must be at least 8 characters.", file=sys.stderr)
        return 1

    _apply_local_defaults()
    _patch_get_secret_for_local_dev()

    print(f"Provisioning visitor: {args.email} ({args.name})")
    print("-" * 60)

    result = _provision_visitor(args.email, args.password, args.name)
    successes = result["successes"]
    failures = result["failures"]

    if successes:
        print(f"\nSucceeded ({len(successes)} service(s)):")
        for entry in successes:
            print(f"  {entry['service']}: {json.dumps(entry['result'])}")

    if failures:
        print(f"\nFailed ({len(failures)} service(s)):")
        for entry in failures:
            print(f"  {entry['service']}: {entry['error']}", file=sys.stderr)

    print()
    if not successes:
        print("All services failed — no accounts were provisioned.", file=sys.stderr)
        return 1

    return 0 if not failures else 0  # partial success is still exit 0


if __name__ == "__main__":
    sys.exit(main())
