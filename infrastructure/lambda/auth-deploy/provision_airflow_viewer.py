"""Airflow viewer account provisioning module.

Creates or updates an Airflow user account with the built-in FAB ``Viewer``
role. Works against any Airflow instance reachable via HTTP — local Docker
Compose (port 8082) and the production EKS deployment use the same stable
REST API surface at ``/api/v1/users``.

The provisioner is idempotent: a 409 response from the create endpoint means
the user already exists, in which case the account is updated via PATCH with
the current password and the Viewer role re-applied.

Uses only Python stdlib (urllib) to keep the Lambda deployment package lean,
consistent with other provisioning modules and handler.py in the same
directory.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def provision_viewer(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    airflow_url: str,
    admin_user: str,
    admin_password: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create or update an Airflow user account with the FAB Viewer role.

    Idempotent: if the user already exists (HTTP 409 from the create endpoint)
    the existing account is updated via PATCH with the supplied password and
    the Viewer role is (re-)applied.

    Args:
        email: The visitor's email address, used as both username and email in
            Airflow.
        password: The plaintext password for the Airflow account.
        first_name: The user's first name as displayed in Airflow's UI.
        last_name: The user's last name as displayed in Airflow's UI.
        airflow_url: Base URL of the Airflow instance, e.g.
            ``"http://localhost:8082"``.  No trailing slash.
        admin_user: Airflow admin username used for Basic authentication.
        admin_password: Airflow admin password used for Basic authentication.
        **kwargs: Ignored keyword arguments forwarded by the handler dispatcher.

    Returns:
        A dict with the following keys:

        - ``"status"``: ``"created"`` when the user was newly provisioned,
          ``"updated"`` when the user already existed and was refreshed.
        - ``"username"``: The username (email) that was provisioned.

    Raises:
        urllib.error.HTTPError: If an unexpected HTTP error occurs (anything
            other than 409 on the create request).
    """
    credentials = base64.b64encode(f"{admin_user}:{admin_password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    }

    username = email
    status = _create_or_update_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        airflow_url=airflow_url,
        headers=headers,
    )

    return {"status": status, "username": username}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _viewer_role_payload() -> list[dict[str, str]]:
    """Return the roles list containing the FAB Viewer role.

    Returns:
        A list with a single dict ``{"name": "Viewer"}``, matching the shape
        expected by the Airflow REST API for user role assignments.
    """
    return [{"name": "Viewer"}]


def _create_or_update_user(
    username: str,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    airflow_url: str,
    headers: dict[str, str],
) -> str:
    """Attempt to create the user; fall back to PATCH on 409.

    Args:
        username: The username (email) for the Airflow account.
        email: The email address for the Airflow account.
        password: The plaintext password.
        first_name: The user's first name.
        last_name: The user's last name.
        airflow_url: Base Airflow URL.
        headers: Common HTTP headers including Authorization.

    Returns:
        ``"created"`` when the user was newly created, ``"updated"`` when an
        existing user's account was refreshed via PATCH.

    Raises:
        urllib.error.HTTPError: For any HTTP error except 409 on the POST.
    """
    payload = {
        "username": username,
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name,
        "roles": _viewer_role_payload(),
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url=f"{airflow_url}/api/v1/users",
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req):
            return "created"
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            _update_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                airflow_url=airflow_url,
                headers=headers,
            )
            return "updated"
        raise


def _update_user(
    username: str,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    airflow_url: str,
    headers: dict[str, str],
) -> None:
    """Patch an existing Airflow user's password and role.

    Args:
        username: The Airflow username (email) to update.
        email: The email address for the account.
        password: The new plaintext password.
        first_name: The user's first name.
        last_name: The user's last name.
        airflow_url: Base Airflow URL.
        headers: Common HTTP headers including Authorization.

    Raises:
        urllib.error.HTTPError: If the PATCH request fails.
    """
    payload = {
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name,
        "roles": _viewer_role_payload(),
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url=f"{airflow_url}/api/v1/users/{username}",
        data=body,
        headers=headers,
        method="PATCH",
    )
    with urllib.request.urlopen(req):
        pass
