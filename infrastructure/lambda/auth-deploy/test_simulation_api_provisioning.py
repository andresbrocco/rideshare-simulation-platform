"""Unit tests for Simulation API viewer account provisioning.

Tests validate the behavioural scenarios for provision_viewer() in
provision_simulation_api_viewer.py, and verify the handler's
_provision_simulation_api delegates to _load_module.

Scenarios covered:
- New user creation (HTTP 201 from POST /auth/register)
- Idempotent update of an existing user (HTTP 200 from POST /auth/register)
- Correct headers are sent (X-API-Key, Content-Type, POST method, /auth/register path)
- Correct request body is sent (email, password, name as JSON)
- Unexpected HTTP errors (e.g. 503) propagate to the caller
- handler._provision_simulation_api calls _load_module with the correct module name

These are pure unit tests — no running services required.
"""

from __future__ import annotations

import importlib.util
import io
import json
import types
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

# Paths resolved from this test file's location (infrastructure/lambda/auth-deploy/).
_PROVISION_MODULE_PATH = Path(__file__).parent / "provision_simulation_api_viewer.py"
_MODULE_NAME = "provision_simulation_api_viewer"

# Shared test constants
_SIMULATION_URL = "https://api.ridesharing.portfolio.andresbrocco.com"
_ADMIN_API_KEY = "test-admin-api-key"
_EMAIL = "visitor@example.com"
_PASSWORD = "s3cret!1"
_NAME = "Test Visitor"


def _load_provision_module() -> types.ModuleType:
    """Load provision_simulation_api_viewer.py as a module object.

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
        url=f"{_SIMULATION_URL}/auth/register",
        code=code,
        msg=message,
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(message.encode()),
    )


# ---------------------------------------------------------------------------
# Tests for provision_simulation_api_viewer.provision_viewer()
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_provision_viewer_creates_user() -> None:
    """provision_viewer() returns status='created' when the API responds with HTTP 201.

    When POST /auth/register responds with 201 (Created) the provisioner
    should report status='created' in the result dict.
    """
    module = _load_provision_module()

    response_body = {"email": _EMAIL, "role": "viewer"}
    create_response = _make_response(response_body, status=201)

    with patch.object(module.urllib.request, "urlopen", return_value=create_response):
        result = module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            name=_NAME,
            simulation_url=_SIMULATION_URL,
            admin_api_key=_ADMIN_API_KEY,
        )

    assert result["status"] == "created", f"Expected 'created', got: {result['status']!r}"


@pytest.mark.unit
def test_provision_viewer_updates_existing_user() -> None:
    """provision_viewer() returns status='updated' when the API responds with HTTP 200.

    The /auth/register endpoint is idempotent: re-registering an existing
    email with HTTP 200 (OK) signals an update rather than a new creation.
    The provisioner should report status='updated' in that case.
    """
    module = _load_provision_module()

    response_body = {"email": _EMAIL, "role": "viewer"}
    update_response = _make_response(response_body, status=200)

    with patch.object(module.urllib.request, "urlopen", return_value=update_response):
        result = module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            name=_NAME,
            simulation_url=_SIMULATION_URL,
            admin_api_key=_ADMIN_API_KEY,
        )

    assert result["status"] == "updated", f"Expected 'updated', got: {result['status']!r}"


@pytest.mark.unit
def test_provision_viewer_sends_correct_headers() -> None:
    """provision_viewer() sends X-API-Key header, uses POST method, and targets /auth/register.

    The request must:
    - Use the POST HTTP method
    - Target a URL containing /auth/register
    - Include the X-API-Key header set to the provided admin_api_key value
    """
    module = _load_provision_module()

    response_body = {"email": _EMAIL, "role": "viewer"}
    create_response = _make_response(response_body, status=201)
    captured_requests: list[Any] = []

    def urlopen_side_effect(req: Any, **kwargs: Any) -> Any:
        captured_requests.append(req)
        return create_response

    with patch.object(module.urllib.request, "urlopen", side_effect=urlopen_side_effect):
        module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            name=_NAME,
            simulation_url=_SIMULATION_URL,
            admin_api_key=_ADMIN_API_KEY,
        )

    assert (
        len(captured_requests) == 1
    ), f"Expected exactly 1 HTTP call, got {len(captured_requests)}"
    req = captured_requests[0]

    assert req.get_method() == "POST", f"Expected POST method, got: {req.get_method()!r}"
    assert (
        "/auth/register" in req.full_url
    ), f"Expected /auth/register in URL, got: {req.full_url!r}"
    api_key_header = req.get_header("X-api-key")
    assert (
        api_key_header == _ADMIN_API_KEY
    ), f"Expected X-API-Key={_ADMIN_API_KEY!r}, got: {api_key_header!r}"


@pytest.mark.unit
def test_provision_viewer_sends_correct_body() -> None:
    """provision_viewer() sends a JSON body containing email, password, and name.

    The request body must be valid JSON with at minimum the keys
    'email', 'password', and 'name' set to the values passed to provision_viewer().
    """
    module = _load_provision_module()

    response_body = {"email": _EMAIL, "role": "viewer"}
    create_response = _make_response(response_body, status=201)
    captured_requests: list[Any] = []

    def urlopen_side_effect(req: Any, **kwargs: Any) -> Any:
        captured_requests.append(req)
        return create_response

    with patch.object(module.urllib.request, "urlopen", side_effect=urlopen_side_effect):
        module.provision_viewer(
            email=_EMAIL,
            password=_PASSWORD,
            name=_NAME,
            simulation_url=_SIMULATION_URL,
            admin_api_key=_ADMIN_API_KEY,
        )

    assert (
        len(captured_requests) == 1
    ), f"Expected exactly 1 HTTP call, got {len(captured_requests)}"
    req = captured_requests[0]
    body: dict[str, str] = json.loads(req.data)

    assert (
        body.get("email") == _EMAIL
    ), f"Expected email={_EMAIL!r} in body, got: {body.get('email')!r}"
    assert (
        body.get("password") == _PASSWORD
    ), f"Expected password in body, got: {body.get('password')!r}"
    assert body.get("name") == _NAME, f"Expected name={_NAME!r} in body, got: {body.get('name')!r}"


@pytest.mark.unit
def test_provision_viewer_propagates_http_errors() -> None:
    """provision_viewer() propagates urllib.error.HTTPError for non-idempotent failures.

    A 503 Service Unavailable from the Simulation API should not be swallowed
    — it must bubble up to the caller so the orchestrator can handle or
    report it.
    """
    module = _load_provision_module()

    with patch.object(
        module.urllib.request,
        "urlopen",
        side_effect=_make_http_error(503, "Service Unavailable"),
    ):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            module.provision_viewer(
                email=_EMAIL,
                password=_PASSWORD,
                name=_NAME,
                simulation_url=_SIMULATION_URL,
                admin_api_key=_ADMIN_API_KEY,
            )

    assert (
        exc_info.value.code == 503
    ), f"Expected HTTPError with code 503, got: {exc_info.value.code}"


# ---------------------------------------------------------------------------
# Tests for handler._provision_simulation_api using _load_module
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_handler_provision_simulation_api_uses_load_module() -> None:
    """handler._provision_simulation_api delegates to _load_module with the correct args.

    The refactored handler must call _load_module("provision_simulation_api_viewer",
    scripts_dir) and invoke provision_viewer on the returned module, rather than
    implementing inline HTTP logic.
    """
    import handler as handler_module

    mock_provision_result = {"status": "created", "email": _EMAIL}
    mock_viewer_module = MagicMock()
    mock_viewer_module.provision_viewer.return_value = mock_provision_result

    scripts_dir = str(Path(__file__).parent)

    with (
        patch.object(handler_module, "_load_module", return_value=mock_viewer_module) as mock_load,
        patch.object(handler_module, "get_secret", return_value=_ADMIN_API_KEY),
        patch.dict("os.environ", {"SIMULATION_API_URL": _SIMULATION_URL}),
    ):
        result = handler_module._provision_simulation_api(
            email=_EMAIL,
            password=_PASSWORD,
            name=_NAME,
            scripts_dir=scripts_dir,
        )

    mock_load.assert_called_once_with("provision_simulation_api_viewer", scripts_dir)
    mock_viewer_module.provision_viewer.assert_called_once()
    assert result == mock_provision_result
