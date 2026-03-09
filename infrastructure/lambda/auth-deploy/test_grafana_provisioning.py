"""Unit tests for Grafana viewer account provisioning.

Tests validate the four behavioural scenarios for provision_viewer():
- New user creation (HTTP 200 from POST /api/admin/users)
- Idempotent handling of existing users (HTTP 412 → GET lookup → PATCH)
- The org role is always set to Viewer regardless of path
- Unexpected HTTP errors (non-412) are propagated to the caller

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
# test_grafana_provisioning.py lives at infrastructure/lambda/auth-deploy/
# The canonical provisioning script is co-located in the same directory.
_PROVISION_MODULE_PATH = __import__("pathlib").Path(__file__).parent / "provision_grafana_viewer.py"

# Module name used when registering in sys.modules via importlib.
_MODULE_NAME = "provision_grafana_viewer"

# Shared test constants
_GRAFANA_URL = "http://localhost:3001"
_ADMIN_AUTH = "Basic YWRtaW46YWRtaW4="
_EMAIL = "visitor@example.com"
_PASSWORD = "s3cret!"
_NAME = "Test Visitor"


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


def _load_provision_module() -> types.ModuleType:
    """Load provision_grafana_viewer.py as a module object.

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


def _make_response(body: dict[str, Any], status: int = 200) -> MagicMock:
    """Build a MagicMock that acts like a urllib HTTP response context manager."""
    encoded = json.dumps(body).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = encoded
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_http_error(code: int, message: str = "error") -> urllib.error.HTTPError:
    """Build a urllib.error.HTTPError with the given status code."""
    return urllib.error.HTTPError(
        url="http://localhost:3001/api/admin/users",
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
    """provision_viewer() returns status='created' and the correct user_id on success.

    When POST /api/admin/users responds with 200 and {"id": 42, ...} the
    provisioner should report status='created' and user_id=42.
    The org role PATCH should also be called exactly once.
    """
    module = _load_provision_module()

    create_response = _make_response({"id": 42, "message": "User created"})
    patch_response = _make_response({})

    side_effects = [create_response, patch_response]

    with patch.object(module.urllib.request, "urlopen", side_effect=side_effects):
        result = module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            name=_NAME,
            grafana_url=_GRAFANA_URL,
            admin_auth_header=_ADMIN_AUTH,
        )

    assert result["status"] == "created", f"Expected 'created', got: {result['status']}"
    assert result["user_id"] == 42, f"Expected user_id=42, got: {result['user_id']}"


@pytest.mark.unit
def test_handle_existing_user() -> None:
    """provision_viewer() returns status='updated' when POST /api/admin/users returns 412.

    The provisioner must catch the 412, look up the user by email, and return
    status='updated' with the ID returned by the GET lookup endpoint.
    """
    module = _load_provision_module()

    lookup_response = _make_response({"id": 99, "email": _EMAIL})
    patch_response = _make_response({})

    def urlopen_side_effect(req: Any, **kwargs: Any) -> Any:
        # First call is POST (create) → raise 412
        if hasattr(req, "get_method") and req.get_method() == "POST":
            raise _make_http_error(412, "User already exists")
        # Second call is GET (lookup) → return user dict
        if hasattr(req, "get_method") and req.get_method() == "GET":
            return lookup_response
        # Third call is PATCH (set role)
        return patch_response

    with patch.object(module.urllib.request, "urlopen", side_effect=urlopen_side_effect):
        result = module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            name=_NAME,
            grafana_url=_GRAFANA_URL,
            admin_auth_header=_ADMIN_AUTH,
        )

    assert result["status"] == "updated", f"Expected 'updated', got: {result['status']}"
    assert result["user_id"] == 99, f"Expected user_id=99, got: {result['user_id']}"


@pytest.mark.unit
def test_role_set_to_viewer() -> None:
    """provision_viewer() always issues a PATCH with role='Viewer'.

    Regardless of whether the user was newly created or already existed, the
    PATCH request body must contain exactly {"role": "Viewer"}.
    """
    module = _load_provision_module()

    create_response = _make_response({"id": 7, "message": "User created"})
    patch_response = _make_response({})

    captured_requests: list[Any] = []

    def urlopen_side_effect(req: Any, **kwargs: Any) -> Any:
        captured_requests.append(req)
        if len(captured_requests) == 1:
            return create_response
        return patch_response

    with patch.object(module.urllib.request, "urlopen", side_effect=urlopen_side_effect):
        module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            name=_NAME,
            grafana_url=_GRAFANA_URL,
            admin_auth_header=_ADMIN_AUTH,
        )

    assert (
        len(captured_requests) == 2
    ), f"Expected exactly 2 HTTP calls (POST + PATCH), got {len(captured_requests)}"

    patch_req = captured_requests[1]
    assert (
        patch_req.get_method() == "PATCH"
    ), f"Expected second request to be PATCH, got {patch_req.get_method()}"

    patch_body: dict[str, str] = json.loads(patch_req.data)
    assert patch_body == {
        "role": "Viewer"
    }, f'Expected PATCH body {{"role": "Viewer"}}, got: {patch_body}'


@pytest.mark.unit
def test_raises_on_unexpected_error() -> None:
    """provision_viewer() propagates urllib.error.HTTPError for non-412 status codes.

    A 500 Internal Server Error from Grafana should not be swallowed — it must
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
                name=_NAME,
                grafana_url=_GRAFANA_URL,
                admin_auth_header=_ADMIN_AUTH,
            )

    assert (
        exc_info.value.code == 500
    ), f"Expected HTTPError with code 500, got: {exc_info.value.code}"
