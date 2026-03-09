"""MinIO visitor account provisioning module.

Creates or updates a MinIO user account with read-only access to the
rideshare-gold bucket. Works identically against local MinIO (Docker Compose)
and production AWS S3 IAM-compatible endpoints.

The read-only policy is loaded from a ``minio-visitor-readonly.json`` file
co-located in this directory, with a fallback to the canonical location at
``infrastructure/policies/minio-visitor-readonly.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from minio import MinioAdmin
from minio.credentials.providers import StaticProvider
from minio.error import MinioAdminException

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POLICY_NAME = "visitor-readonly"

# Prefer a co-located policy document (bundled inside the Lambda zip).
# Fall back to the canonical infrastructure/policies/ location when running
# directly from the repository (e.g. during local dev or CI).
_POLICY_FILE_COLOCATED = Path(__file__).parent / "minio-visitor-readonly.json"
_POLICY_FILE_CANONICAL = (
    Path(__file__).parent.parent.parent
    / "infrastructure"
    / "policies"
    / "minio-visitor-readonly.json"
)
_POLICY_FILE = _POLICY_FILE_COLOCATED if _POLICY_FILE_COLOCATED.exists() else _POLICY_FILE_CANONICAL


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def provision_visitor(
    email: str,
    password: str,
    endpoint: str,
    access_key: str,
    secret_key: str,
    **kwargs: Any,
) -> dict[str, str]:
    """Create or update a MinIO visitor account with read-only gold-bucket access.

    Idempotent: if the user already exists the password is updated and the
    policy is re-applied.  The ``visitor-readonly`` policy is registered (or
    re-registered) on every call so that the policy definition stays in sync
    with the JSON file.

    The MinIO ``user_add`` endpoint is a PUT that creates or updates atomically,
    so this function checks for prior existence via ``user_info`` to determine
    the return status without relying on error-path idempotency.

    Args:
        email: The visitor's email address, used as the MinIO access key.
        password: The plaintext password / secret key for the account.
        endpoint: MinIO endpoint without scheme, e.g. ``"localhost:9000"``.
        access_key: Admin access key used to authenticate against MinIO.
        secret_key: Admin secret key used to authenticate against MinIO.
        **kwargs: Accepted for forward-compatibility with the handler's
            provisioning call convention; currently unused.

    Returns:
        A dict with the following keys:

        - ``"status"``: ``"created"`` if the user was newly created,
          ``"updated"`` if an existing user was updated.
        - ``"email"``: The visitor email that was provisioned.

    Raises:
        MinioAdminException: If an unexpected MinIO admin API error occurs
            (i.e. one that is not a user-not-found condition on the info call).
    """
    admin = MinioAdmin(
        endpoint=endpoint,
        credentials=StaticProvider(access_key, secret_key),
        secure=False,
    )

    policy_doc: dict[str, Any] = json.loads(_POLICY_FILE.read_text())
    admin.policy_add(_POLICY_NAME, policy=policy_doc)

    status = _upsert_user(admin, email, password)
    admin.policy_set(_POLICY_NAME, user=email)

    return {"status": status, "email": email}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _upsert_user(
    admin: MinioAdmin,
    email: str,
    password: str,
) -> str:
    """Add a new MinIO user or update the password of an existing one.

    Checks for prior existence via ``user_info`` then calls ``user_add`` to
    create or update.  The ``user_add`` PUT endpoint is idempotent in MinIO —
    it creates or overwrites the secret key without raising on duplicates.

    Args:
        admin: An authenticated :class:`minio.MinioAdmin` instance.
        email: The access key / username.
        password: The secret key / password.

    Returns:
        ``"created"`` when a new user was added, ``"updated"`` when an
        existing user's password was refreshed.

    Raises:
        MinioAdminException: If an unexpected admin API error occurs other
            than the user-not-found condition on the ``user_info`` call.
    """
    user_exists = _user_exists(admin, email)
    admin.user_add(email, password)
    return "updated" if user_exists else "created"


def _user_exists(admin: MinioAdmin, email: str) -> bool:
    """Return True if the given user already exists in MinIO.

    Args:
        admin: An authenticated :class:`minio.MinioAdmin` instance.
        email: The access key / username to look up.

    Returns:
        ``True`` if the user exists, ``False`` if it does not.

    Raises:
        MinioAdminException: If the error from MinIO is not a not-found
            condition (unexpected errors are re-raised).
    """
    try:
        admin.user_info(email)
        return True
    except MinioAdminException as exc:
        if _is_not_found_error(exc):
            return False
        raise


def _is_not_found_error(exc: MinioAdminException) -> bool:
    """Return True when the exception signals a user-not-found condition.

    MinIO returns a JSON body like ``{"Code": "XMinioAdminNoSuchUser", ...}``
    for missing users.  This helper checks both the canonical error code and
    common message substrings for robustness across MinIO versions.

    Args:
        exc: The :class:`~minio.error.MinioAdminException` to inspect.

    Returns:
        ``True`` if the exception represents a user-not-found error.
    """
    body = str(exc).lower()
    not_found_signals = (
        "xminioadminnosuchuser",
        "not found",
        "does not exist",
        "no such user",
    )
    return any(signal in body for signal in not_found_signals)
