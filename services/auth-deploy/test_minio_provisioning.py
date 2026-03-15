"""Unit tests for MinIO read-only IAM policy and visitor provisioning.

Tests validate:
- Policy document structure and constraints (no PutObject, scoped to gold only)
- provision_visitor() creation path
- provision_visitor() idempotency (update-on-existing path)

These tests are pure unit tests — no running services required.
"""

from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Paths resolved from this test file's location.
# test_minio_provisioning.py lives at services/auth-deploy/
# Repository root is three levels up: auth-deploy -> services -> repo-root
_REPO_ROOT = Path(__file__).parent.parent.parent
_POLICY_FILE = _REPO_ROOT / "infrastructure" / "policies" / "minio-visitor-readonly.json"
_PROVISION_MODULE_PATH = Path(__file__).parent / "provision_minio_visitor.py"

# Module name used when registering in sys.modules via importlib.
_MODULE_NAME = "provision_minio_visitor"


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


def _load_provision_module() -> types.ModuleType:
    """Load provision_minio_visitor.py as a module object.

    Returns the module so callers can patch its namespace directly, which is
    required because the module binds ``MinioAdmin`` and ``StaticProvider`` at
    import time via ``from minio import ...``.
    """
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _PROVISION_MODULE_PATH)
    assert spec is not None, f"Could not locate module spec at {_PROVISION_MODULE_PATH}"
    assert spec.loader is not None
    module: types.ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def policy() -> dict[str, Any]:
    """Load and return the parsed minio-visitor-readonly.json policy."""
    content = _POLICY_FILE.read_text()
    return json.loads(content)  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def all_resources(policy: dict[str, Any]) -> list[str]:
    """Collect all Resource values across every Statement in the policy."""
    resources: list[str] = []
    for statement in policy.get("Statement", []):
        res = statement.get("Resource", [])
        if isinstance(res, str):
            resources.append(res)
        else:
            resources.extend(res)
    return resources


@pytest.fixture(scope="module")
def all_actions(policy: dict[str, Any]) -> list[str]:
    """Collect all Action values across every Statement in the policy."""
    actions: list[str] = []
    for statement in policy.get("Statement", []):
        act = statement.get("Action", [])
        if isinstance(act, str):
            actions.append(act)
        else:
            actions.extend(act)
    return actions


# ---------------------------------------------------------------------------
# Policy JSON structural tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_policy_json_valid() -> None:
    """Policy document at infrastructure/policies/minio-visitor-readonly.json must parse as valid JSON."""
    content = _POLICY_FILE.read_text()
    parsed = json.loads(content)
    assert isinstance(parsed, dict), "Policy root must be a JSON object"


@pytest.mark.unit
def test_policy_allows_getobject(all_resources: list[str], all_actions: list[str]) -> None:
    """Policy must grant s3:GetObject scoped to the rideshare-gold bucket."""
    assert any(
        action in ("s3:GetObject", "s3:*") for action in all_actions
    ), "Expected s3:GetObject in policy Actions"
    assert any(
        "rideshare-gold" in resource for resource in all_resources
    ), "Expected rideshare-gold bucket referenced in Resources for GetObject"


@pytest.mark.unit
def test_policy_allows_listbucket(all_resources: list[str], all_actions: list[str]) -> None:
    """Policy must grant s3:ListBucket scoped to the rideshare-gold bucket."""
    assert any(
        action in ("s3:ListBucket", "s3:*") for action in all_actions
    ), "Expected s3:ListBucket in policy Actions"
    assert any(
        "rideshare-gold" in resource for resource in all_resources
    ), "Expected rideshare-gold bucket referenced in Resources for ListBucket"


@pytest.mark.unit
def test_policy_no_putobject(all_actions: list[str]) -> None:
    """Policy must not contain s3:PutObject in any Statement."""
    assert (
        "s3:PutObject" not in all_actions
    ), "Policy must not grant s3:PutObject — visitors have read-only access"


@pytest.mark.unit
def test_policy_no_bronze_access(all_resources: list[str]) -> None:
    """Policy must not reference rideshare-bronze in any Resource."""
    bronze_resources = [r for r in all_resources if "rideshare-bronze" in r]
    assert (
        not bronze_resources
    ), f"Policy must not grant access to rideshare-bronze bucket, found: {bronze_resources}"


@pytest.mark.unit
def test_policy_no_silver_access(all_resources: list[str]) -> None:
    """Policy must not reference rideshare-silver in any Resource."""
    silver_resources = [r for r in all_resources if "rideshare-silver" in r]
    assert (
        not silver_resources
    ), f"Policy must not grant access to rideshare-silver bucket, found: {silver_resources}"


# ---------------------------------------------------------------------------
# provision_visitor() behavioural tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_provision_creates_user() -> None:
    """provision_visitor() returns status='created' when the user does not yet exist.

    MinIO's user_info raises MinioAdminException when the user is not found.
    The provisioner catches that, calls user_add to create the account, and
    reports status='created'.

    Patching is applied to the loaded module's own namespace because the module
    binds ``MinioAdmin`` at import time via ``from minio import MinioAdmin``.
    """
    from minio.error import MinioAdminException

    module = _load_provision_module()

    mock_admin = MagicMock()
    # user_info raises not-found → user does not yet exist
    mock_admin.user_info.side_effect = MinioAdminException(
        "404", '{"Code": "XMinioAdminNoSuchUser"}'
    )
    mock_admin.user_add.return_value = None
    mock_admin.policy_set.return_value = None

    # Patch the names as they appear in the loaded module's __dict__
    with (
        patch.object(module, "MinioAdmin", return_value=mock_admin),
        patch.object(module, "StaticProvider"),
    ):
        result = module.provision_visitor(
            email="newvisitor@test.com",
            password="testpass123",
            endpoint="localhost:9000",
            access_key="admin",
            secret_key="adminadmin",
        )

    assert result["status"] == "created", f"Expected 'created', got: {result}"
    assert result["email"] == "newvisitor@test.com"
    mock_admin.user_add.assert_called_once()
    mock_admin.policy_set.assert_called_once()


@pytest.mark.unit
def test_provision_updates_existing() -> None:
    """provision_visitor() returns status='updated' when the user already exists.

    When user_info succeeds (returns without raising), the user exists.
    The provisioner calls user_add to update the password and reports
    status='updated'.
    """
    module = _load_provision_module()

    mock_admin = MagicMock()
    # user_info succeeds → user already exists
    mock_admin.user_info.return_value = '{"status": "enabled"}'
    mock_admin.user_add.return_value = None
    mock_admin.policy_set.return_value = None

    with (
        patch.object(module, "MinioAdmin", return_value=mock_admin),
        patch.object(module, "StaticProvider"),
    ):
        result = module.provision_visitor(
            email="existing@test.com",
            password="newpass456",
            endpoint="localhost:9000",
            access_key="admin",
            secret_key="adminadmin",
        )

    assert result["status"] == "updated", f"Expected 'updated', got: {result}"
    assert result["email"] == "existing@test.com"
    mock_admin.user_add.assert_called_once()
    mock_admin.policy_set.assert_called_once()
