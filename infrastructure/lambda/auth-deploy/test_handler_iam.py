"""Unit tests for Lambda IAM permission fixes: Secrets Manager and SES configuration.

Tests validate:
- SECRET_GRAFANA_ADMIN_PASSWORD constant matches the Terraform-created secret name
  (rideshare/monitoring), not the old rideshare/grafana-admin-password value.
- _provision_grafana parses the JSON-encoded monitoring secret to extract ADMIN_PASSWORD.
- _provision_grafana falls back to the GRAFANA_ADMIN_PASSWORD env var without calling
  get_secret when the env var is set.

These are pure unit tests — no running services or AWS credentials required.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

_HANDLER_PATH = __import__("pathlib").Path(__file__).parent / "handler.py"
_MODULE_NAME = "handler"


def _load_handler() -> types.ModuleType:
    """Load handler.py as a module object.

    Uses importlib so the module is imported without executing the Lambda
    entry point.  boto3 / botocore are available in the local venv so import
    succeeds without stubs.
    """
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _HANDLER_PATH)
    assert spec is not None, f"Could not locate module spec at {_HANDLER_PATH}"
    assert spec.loader is not None
    module: types.ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_secret_grafana_constant_matches_terraform() -> None:
    """SECRET_GRAFANA_ADMIN_PASSWORD must equal 'rideshare/monitoring'.

    Terraform creates the monitoring secret under the key rideshare/monitoring
    (not rideshare/grafana-admin-password).  The constant in handler.py must
    match so that get_secret resolves the correct ARN.
    """
    module = _load_handler()
    assert (
        module.SECRET_GRAFANA_ADMIN_PASSWORD == "rideshare/monitoring"
    ), f"Expected 'rideshare/monitoring', got: {module.SECRET_GRAFANA_ADMIN_PASSWORD!r}"


@pytest.mark.unit
def test_provision_grafana_parses_monitoring_secret() -> None:
    """_provision_grafana must parse ADMIN_PASSWORD from the JSON monitoring secret.

    The rideshare/monitoring secret is JSON-encoded and contains multiple
    fields (ADMIN_USER, ADMIN_PASSWORD, …).  _provision_grafana must parse
    the JSON and extract ADMIN_PASSWORD to build the Basic auth header.

    The admin_auth_header passed to provision_viewer must be base64 of
    'admin:supersecret'.
    """
    module = _load_handler()

    # JSON secret returned by Secrets Manager for rideshare/monitoring
    monitoring_secret_json = json.dumps({"ADMIN_USER": "admin", "ADMIN_PASSWORD": "supersecret"})

    captured_calls: list[dict[str, Any]] = []

    def fake_provision_viewer(
        *,
        email: str,
        password: str,
        name: str,
        grafana_url: str,
        admin_auth_header: str,
    ) -> dict[str, Any]:
        captured_calls.append({"admin_auth_header": admin_auth_header})
        return {"status": "created", "user_id": 1}

    fake_module = MagicMock()
    fake_module.provision_viewer = fake_provision_viewer

    with (
        patch.object(module, "get_secret", return_value=monitoring_secret_json),
        patch.object(module, "_load_module", return_value=fake_module),
        patch.dict(os.environ, {}, clear=False),
    ):
        # Remove env var override so the code falls through to get_secret.
        os.environ.pop("GRAFANA_ADMIN_PASSWORD", None)
        module._provision_grafana(
            email="visitor@example.com",
            password="visitorpass",
            name="Test Visitor",
            scripts_dir="/fake/scripts",
        )

    assert (
        len(captured_calls) == 1
    ), f"Expected exactly 1 call to provision_viewer, got {len(captured_calls)}"

    admin_auth_header = captured_calls[0]["admin_auth_header"]
    expected_credentials = base64.b64encode(b"admin:supersecret").decode()
    expected_header = f"Basic {expected_credentials}"

    assert (
        admin_auth_header == expected_header
    ), f"Expected admin_auth_header={expected_header!r}, got {admin_auth_header!r}"


@pytest.mark.unit
def test_provision_grafana_falls_back_to_env_var() -> None:
    """_provision_grafana must not call get_secret when GRAFANA_ADMIN_PASSWORD is set.

    When the environment variable is present the function must use it directly
    and skip the Secrets Manager lookup entirely.
    """
    module = _load_handler()

    captured_calls: list[dict[str, Any]] = []

    def fake_provision_viewer(
        *,
        email: str,
        password: str,
        name: str,
        grafana_url: str,
        admin_auth_header: str,
    ) -> dict[str, Any]:
        captured_calls.append({"admin_auth_header": admin_auth_header})
        return {"status": "created", "user_id": 2}

    fake_module = MagicMock()
    fake_module.provision_viewer = fake_provision_viewer

    mock_get_secret = MagicMock()

    with (
        patch.object(module, "get_secret", mock_get_secret),
        patch.object(module, "_load_module", return_value=fake_module),
        patch.dict(os.environ, {"GRAFANA_ADMIN_PASSWORD": "envpassword"}, clear=False),
    ):
        module._provision_grafana(
            email="visitor@example.com",
            password="visitorpass",
            name="Test Visitor",
            scripts_dir="/fake/scripts",
        )

    mock_get_secret.assert_not_called()

    assert (
        len(captured_calls) == 1
    ), f"Expected exactly 1 call to provision_viewer, got {len(captured_calls)}"

    admin_auth_header = captured_calls[0]["admin_auth_header"]
    expected_credentials = base64.b64encode(b"admin:envpassword").decode()
    expected_header = f"Basic {expected_credentials}"

    assert (
        admin_auth_header == expected_header
    ), f"Expected admin_auth_header={expected_header!r}, got {admin_auth_header!r}"
