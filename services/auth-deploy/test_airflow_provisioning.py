"""Unit tests for Airflow viewer account provisioning.

Tests validate the five behavioural scenarios for provision_viewer():
- New user creation (HTTP 200 from POST /api/v1/users)
- Idempotent handling of existing users (HTTP 409 → PATCH /api/v1/users/{username})
- The Viewer role is included in the create request body
- The Viewer role is included in the PATCH request body on update
- Unexpected HTTP errors (non-409) are propagated to the caller

These tests are pure unit tests — no running services required.
"""

from __future__ import annotations

import importlib.util
import io
import json
import types
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Paths resolved from this test file's location.
# test_airflow_provisioning.py lives at services/auth-deploy/
# Repository root is four levels up: auth-deploy -> lambda -> infrastructure -> repo-root
_PROVISION_MODULE_PATH = __import__("pathlib").Path(__file__).parent / "provision_airflow_viewer.py"

# Module name used when registering in sys.modules via importlib.
_MODULE_NAME = "provision_airflow_viewer"

# Shared test constants
_AIRFLOW_URL = "http://localhost:8082"
_ADMIN_USER = "admin"
_ADMIN_PASSWORD = "admin"
_EMAIL = "visitor@test.com"
_PASSWORD = "s3cret!"
_FIRST_NAME = "Test"
_LAST_NAME = "Visitor"


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


def _load_provision_module() -> types.ModuleType:
    """Load provision_airflow_viewer.py as a module object.

    Loads it fresh each time so that patches applied in one test do not bleed
    into another.  The module uses only stdlib so no additional stubs are
    required during import.
    """
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _PROVISION_MODULE_PATH)
    assert spec is not None, f"Could not locate module spec at {_PROVISION_MODULE_PATH}"
    assert spec.loader is not None
    module: types.ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Helpers to build mock HTTP responses
# ---------------------------------------------------------------------------


def _make_response(body: dict[str, Any] | None = None, status: int = 200) -> MagicMock:
    """Build a MagicMock that acts like a urllib HTTP response context manager."""
    encoded = json.dumps(body or {}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = encoded
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_http_error(code: int, message: str = "error") -> urllib.error.HTTPError:
    """Build a urllib.error.HTTPError with the given status code."""
    return urllib.error.HTTPError(
        url=f"{_AIRFLOW_URL}/api/v1/users",
        code=code,
        msg=message,
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(message.encode()),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_new_user() -> None:
    """provision_viewer() returns status='created' and the correct username on success.

    When POST /api/v1/users responds with 200 the provisioner should report
    status='created' and username equal to the email.
    """
    module = _load_provision_module()

    create_response = _make_response({"username": _EMAIL})

    with patch.object(module.urllib.request, "urlopen", return_value=create_response):
        result = module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            first_name=_FIRST_NAME,
            last_name=_LAST_NAME,
            airflow_url=_AIRFLOW_URL,
            admin_user=_ADMIN_USER,
            admin_password=_ADMIN_PASSWORD,
        )

    assert result["status"] == "created", f"Expected 'created', got: {result['status']}"
    assert result["username"] == _EMAIL, f"Expected username={_EMAIL!r}, got: {result['username']}"


@pytest.mark.unit
def test_handle_existing_user_409() -> None:
    """provision_viewer() returns status='updated' when POST /api/v1/users returns 409.

    The provisioner must catch the 409, issue a PATCH to update the existing
    account, and return status='updated' with the correct username.
    """
    module = _load_provision_module()

    patch_response = _make_response({"username": _EMAIL})

    def urlopen_side_effect(req: Any, **kwargs: Any) -> Any:
        if hasattr(req, "get_method") and req.get_method() == "POST":
            raise _make_http_error(409, "User already exists")
        return patch_response

    with patch.object(module.urllib.request, "urlopen", side_effect=urlopen_side_effect):
        result = module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            first_name=_FIRST_NAME,
            last_name=_LAST_NAME,
            airflow_url=_AIRFLOW_URL,
            admin_user=_ADMIN_USER,
            admin_password=_ADMIN_PASSWORD,
        )

    assert result["status"] == "updated", f"Expected 'updated', got: {result['status']}"
    assert result["username"] == _EMAIL, f"Expected username={_EMAIL!r}, got: {result['username']}"


@pytest.mark.unit
def test_viewer_role_on_create() -> None:
    """Viewer role is included in the POST body when creating a new user.

    The create request body must contain ``"roles": [{"name": "Viewer"}]``
    so that the FAB Viewer role is assigned on account creation.
    """
    module = _load_provision_module()

    create_response = _make_response({"username": _EMAIL})
    captured_requests: list[Any] = []

    def urlopen_side_effect(req: Any, **kwargs: Any) -> Any:
        captured_requests.append(req)
        return create_response

    with patch.object(module.urllib.request, "urlopen", side_effect=urlopen_side_effect):
        module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            first_name=_FIRST_NAME,
            last_name=_LAST_NAME,
            airflow_url=_AIRFLOW_URL,
            admin_user=_ADMIN_USER,
            admin_password=_ADMIN_PASSWORD,
        )

    assert (
        len(captured_requests) == 1
    ), f"Expected exactly 1 HTTP call (POST), got {len(captured_requests)}"
    post_req = captured_requests[0]
    assert post_req.get_method() == "POST", f"Expected POST request, got {post_req.get_method()}"
    body: dict[str, Any] = json.loads(post_req.data)
    assert body.get("roles") == [
        {"name": "Viewer"}
    ], f"Expected roles=[{{\"name\": \"Viewer\"}}] in POST body, got: {body.get('roles')}"


@pytest.mark.unit
def test_viewer_role_on_update() -> None:
    """Viewer role is included in the PATCH body when updating an existing user.

    When the create POST returns 409, the subsequent PATCH request body must
    also contain ``"roles": [{"name": "Viewer"}]`` so that the role is
    re-applied even if it was manually removed from the account.
    """
    module = _load_provision_module()

    patch_response = _make_response({"username": _EMAIL})
    captured_requests: list[Any] = []

    def urlopen_side_effect(req: Any, **kwargs: Any) -> Any:
        captured_requests.append(req)
        if req.get_method() == "POST":
            raise _make_http_error(409, "User already exists")
        return patch_response

    with patch.object(module.urllib.request, "urlopen", side_effect=urlopen_side_effect):
        module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            first_name=_FIRST_NAME,
            last_name=_LAST_NAME,
            airflow_url=_AIRFLOW_URL,
            admin_user=_ADMIN_USER,
            admin_password=_ADMIN_PASSWORD,
        )

    assert (
        len(captured_requests) == 2
    ), f"Expected exactly 2 HTTP calls (POST + PATCH), got {len(captured_requests)}"
    patch_req = captured_requests[1]
    assert (
        patch_req.get_method() == "PATCH"
    ), f"Expected second request to be PATCH, got {patch_req.get_method()}"
    body: dict[str, Any] = json.loads(patch_req.data)
    assert body.get("roles") == [
        {"name": "Viewer"}
    ], f"Expected roles=[{{\"name\": \"Viewer\"}}] in PATCH body, got: {body.get('roles')}"


@pytest.mark.unit
def test_raises_on_unexpected_error() -> None:
    """provision_viewer() propagates urllib.error.HTTPError for non-409 status codes.

    A 500 Internal Server Error from Airflow should not be swallowed — it must
    bubble up to the caller so the orchestrator can handle or report it.
    """
    module = _load_provision_module()

    with patch.object(
        module.urllib.request,
        "urlopen",
        side_effect=_make_http_error(500, "Internal Server Error"),
    ):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            module.provision_viewer(
                email=_EMAIL,
                password=_PASSWORD,
                first_name=_FIRST_NAME,
                last_name=_LAST_NAME,
                airflow_url=_AIRFLOW_URL,
                admin_user=_ADMIN_USER,
                admin_password=_ADMIN_PASSWORD,
            )

    assert (
        exc_info.value.code == 500
    ), f"Expected HTTPError with code 500, got: {exc_info.value.code}"
