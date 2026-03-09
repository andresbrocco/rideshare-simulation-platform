"""Simulation API viewer account provisioning module.

Registers or updates a visitor account in the Simulation API auth store by
calling ``POST /auth/register``.  The endpoint is idempotent — re-posting an
existing email updates the password and returns HTTP 200, while a new
registration returns HTTP 201.

Uses only Python stdlib (urllib) to keep the Lambda deployment package lean,
consistent with handler.py and the other provisioning modules in this
directory.

**Canonical location**: ``infrastructure/lambda/auth-deploy/provision_simulation_api_viewer.py``
"""

from __future__ import annotations

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
    name: str,
    simulation_url: str,
    admin_api_key: str,
    **kwargs: object,
) -> dict[str, Any]:
    """Register or update a viewer account in the Simulation API auth store.

    Sends a ``POST /auth/register`` request to the Simulation API.  The
    endpoint is idempotent:

    - HTTP 201 (Created): the account was newly created — returns
      ``{"status": "created", ...}``.
    - HTTP 200 (OK): the account already existed and was updated — returns
      ``{"status": "updated", ...}``.

    Any other HTTP status (e.g. 4xx, 5xx) is treated as an unrecoverable
    error and the underlying ``urllib.error.HTTPError`` is re-raised so the
    orchestrator can handle or report it.

    Args:
        email: The visitor's email address, used as the account identifier.
        password: The plaintext password for the Simulation API account.
        name: The display name stored alongside the account.
        simulation_url: Base URL of the Simulation API, e.g.
            ``"https://api.ridesharing.portfolio.andresbrocco.com"``.
            No trailing slash.
        admin_api_key: The value of the ``X-API-Key`` header used to
            authenticate the registration request.  The handler resolves this
            from Secrets Manager and passes it in — this script never reads
            environment variables directly.
        **kwargs: Accepted for forward-compatible calls from the handler.
            Extra keyword arguments are silently ignored.

    Returns:
        A dict with at minimum the following key:

        - ``"status"``: ``"created"`` for HTTP 201, ``"updated"`` for HTTP 200.

        Additional keys from the API response body (e.g. ``"email"``,
        ``"role"``) are merged into the returned dict.

    Raises:
        urllib.error.HTTPError: If the Simulation API returns an unexpected
            HTTP error status (anything other than 200 or 201).
    """
    payload = {"email": email, "password": password, "name": name}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url=f"{simulation_url}/auth/register",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": admin_api_key,
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        response_data: dict[str, Any] = json.loads(resp.read())
        status_code: int = resp.status

    outcome = "created" if status_code == 201 else "updated"
    return {"status": outcome, **response_data}
