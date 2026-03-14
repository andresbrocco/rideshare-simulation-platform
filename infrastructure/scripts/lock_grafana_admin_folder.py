"""Lock the Grafana Admin folder so only Org Admins can see it.

Grafana's file-based provisioning creates folders with default permissions that
grant visibility to all org roles (Viewer, Editor, Admin).  This module removes
the explicit Viewer and Editor permissions from the Admin folder, leaving only
the implicit Org Admin access.

Uses only Python stdlib (urllib) to stay consistent with the other provisioning
modules in this directory.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def lock_admin_folder(
    grafana_url: str,
    admin_auth_header: str,
    folder_uid: str = "admin",
) -> dict[str, Any]:
    """Remove default Viewer/Editor permissions from the Admin folder.

    Sets the folder's permission list to an empty array, which removes all
    explicit grants.  Org Admins retain implicit access regardless.

    Args:
        grafana_url: Base URL of the Grafana instance (no trailing slash).
        admin_auth_header: ``Authorization`` header value for an admin user,
            e.g. ``"Basic YWRtaW46YWRtaW4="``.
        folder_uid: UID of the folder to lock.  Defaults to ``"admin"``.

    Returns:
        ``{"status": "locked", "folder_uid": "<uid>"}`` on success, or
        ``{"status": "skipped", "reason": "folder_not_found"}`` when the
        folder has not been created yet (HTTP 404).

    Raises:
        urllib.error.HTTPError: For any HTTP error other than 404.
    """
    url = f"{grafana_url}/api/folders/{folder_uid}/permissions"
    payload = json.dumps({"items": []}).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": admin_auth_header,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
        return {"status": "locked", "folder_uid": folder_uid}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"status": "skipped", "reason": "folder_not_found"}
        raise
