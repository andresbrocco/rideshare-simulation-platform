"""Grafana viewer account provisioning module.

Creates or updates a Grafana user account with the built-in Viewer organization
role. Works against any Grafana instance reachable via HTTP — local Docker Compose
(port 3001) and the production EKS deployment use the same API surface.

The provisioner is idempotent: a 412 response from the create endpoint means the
user already exists, in which case the existing user's ID is resolved via the
lookup endpoint and the org role is (re-)applied.

Uses only Python stdlib (urllib) to keep the Lambda deployment package lean,
consistent with handler.py in the same directory.

**Canonical location**: ``services/auth-deploy/provision_grafana_viewer.py``

The file at ``infrastructure/scripts/provision_grafana_viewer.py`` is a copy kept
for reference and ad-hoc local use. The Lambda handler loads this file via
``_load_module`` at runtime — edits should be made here first.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def provision_viewer(
    email: str,
    password: str,
    name: str,
    grafana_url: str,
    admin_auth_header: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create or update a Grafana user account with the Viewer org role.

    Idempotent: if the user already exists (HTTP 412 from the create endpoint)
    the existing account is looked up by email and the org role is updated to
    ``Viewer`` to ensure the account is in the correct state.

    Args:
        email: The visitor's email address, used as both login and email in
            Grafana.
        password: The plaintext password for the Grafana account.
        name: The display name shown in Grafana's UI.
        grafana_url: Base URL of the Grafana instance, e.g.
            ``"http://localhost:3001"``.  No trailing slash.
        admin_auth_header: Value of the ``Authorization`` header to use for
            all requests, e.g. ``"Basic YWRtaW46YWRtaW4="``.
        **kwargs: Accepted for forward-compatible calls from the handler.
            Extra keyword arguments are silently ignored.

    Returns:
        A dict with the following keys:

        - ``"status"``: ``"created"`` when the user was newly provisioned,
          ``"updated"`` when the user already existed and the role was ensured.
        - ``"user_id"``: The integer Grafana user ID, for orchestrator logging.

    Raises:
        urllib.error.HTTPError: If an unexpected HTTP error occurs (anything
            other than 412 on the create request).
    """
    headers = {
        "Authorization": admin_auth_header,
        "Content-Type": "application/json",
    }

    user_id, status = _create_or_resolve_user(email, password, name, grafana_url, headers)
    _set_org_role(user_id, grafana_url, headers)

    return {"status": status, "user_id": user_id}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _create_or_resolve_user(
    email: str,
    password: str,
    name: str,
    grafana_url: str,
    headers: dict[str, str],
) -> tuple[int, str]:
    """Attempt to create the user; fall back to lookup on 412.

    Args:
        email: The visitor's email / login.
        password: The plaintext password.
        name: The display name.
        grafana_url: Base Grafana URL.
        headers: Common HTTP headers including Authorization.

    Returns:
        A ``(user_id, status)`` tuple where ``status`` is ``"created"`` or
        ``"updated"``.

    Raises:
        urllib.error.HTTPError: For any HTTP error except 412.
    """
    payload = {
        "name": name,
        "email": email,
        "login": email,
        "password": password,
        "OrgId": 1,
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url=f"{grafana_url}/api/admin/users",
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data: dict[str, Any] = json.loads(resp.read())
            return int(data["id"]), "created"
    except urllib.error.HTTPError as exc:
        if exc.code == 412:
            user_id = _lookup_user_id(email, grafana_url, headers)
            return user_id, "updated"
        raise


def _lookup_user_id(
    email: str,
    grafana_url: str,
    headers: dict[str, str],
) -> int:
    """Fetch an existing Grafana user's numeric ID by email.

    Args:
        email: The email address / login to look up.
        grafana_url: Base Grafana URL.
        headers: Common HTTP headers including Authorization.

    Returns:
        The integer user ID from Grafana's user lookup response.

    Raises:
        urllib.error.HTTPError: If the lookup request fails.
    """
    encoded_email = urllib.parse.quote(email, safe="")
    req = urllib.request.Request(
        url=f"{grafana_url}/api/users/lookup?loginOrEmail={encoded_email}",
        headers=headers,
        method="GET",
    )
    with urllib.request.urlopen(req) as resp:
        data: dict[str, Any] = json.loads(resp.read())
        return int(data["id"])


def _set_org_role(
    user_id: int,
    grafana_url: str,
    headers: dict[str, str],
) -> None:
    """Patch the user's organization role to Viewer.

    Args:
        user_id: The Grafana user ID to update.
        grafana_url: Base Grafana URL.
        headers: Common HTTP headers including Authorization.

    Raises:
        urllib.error.HTTPError: If the PATCH request fails.
    """
    payload = {"role": "Viewer"}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url=f"{grafana_url}/api/org/users/{user_id}",
        data=body,
        headers=headers,
        method="PATCH",
    )
    with urllib.request.urlopen(req):
        pass
