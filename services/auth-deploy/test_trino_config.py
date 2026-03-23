"""Unit tests for Trino access-control configuration files.

Validates rules.json schema and access control rules. These tests are pure
file-validation tests — they require no running services.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

# Resolve paths relative to the repository root from the test file's location.
# test_trino_config.py lives at services/auth-deploy/
# Repository root is three levels up: auth-deploy -> services -> repo-root
_REPO_ROOT = Path(__file__).parent.parent.parent
_TRINO_ETC = _REPO_ROOT / "services" / "trino" / "etc"
_RULES_JSON = _TRINO_ETC / "rules.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rules() -> dict[str, list[dict[str, str]]]:
    """Load and return the parsed rules.json contents."""
    return cast(dict[str, list[dict[str, str]]], json.loads(_RULES_JSON.read_text()))


# ---------------------------------------------------------------------------
# rules.json tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rules_json_is_valid() -> None:
    """rules.json must parse as valid JSON without error."""
    content = _RULES_JSON.read_text()
    json.loads(content)  # raises json.JSONDecodeError on failure


@pytest.mark.unit
def test_rules_has_delta_catalog(rules: dict[str, list[dict[str, str]]]) -> None:
    """At least one catalog rule must target the 'delta' catalog."""
    catalog_values = [entry.get("catalog", "") for entry in rules.get("catalogs", [])]
    assert (
        "delta" in catalog_values
    ), "Expected a catalog rule with 'catalog': 'delta' in rules.json"


@pytest.mark.unit
def test_admin_has_full_access(rules: dict[str, list[dict[str, str]]]) -> None:
    """The admin user must be granted 'all' access on at least one catalog rule."""
    admin_entries = [
        entry
        for entry in rules.get("catalogs", [])
        if entry.get("user") == "admin" and entry.get("allow") == "all"
    ]
    assert (
        admin_entries
    ), "Expected at least one catalog rule granting 'allow': 'all' to user 'admin'"


@pytest.mark.unit
def test_wildcard_gets_read_only(rules: dict[str, list[dict[str, str]]]) -> None:
    """At least one wildcard (non-admin) catalog rule must grant 'read-only'."""
    wildcard_readonly_entries = [
        entry
        for entry in rules.get("catalogs", [])
        if entry.get("user") != "admin" and entry.get("allow") == "read-only"
    ]
    assert (
        wildcard_readonly_entries
    ), "Expected at least one catalog rule with 'allow': 'read-only' for non-admin users"


@pytest.mark.unit
def test_system_catalog_denied(rules: dict[str, list[dict[str, str]]]) -> None:
    """The 'system' catalog must be explicitly denied for non-admin users."""
    system_deny_entries = [
        entry
        for entry in rules.get("catalogs", [])
        if entry.get("catalog") == "system"
        and entry.get("user") != "admin"
        and entry.get("allow") == "none"
    ]
    assert system_deny_entries, (
        "Expected a catalog rule with 'catalog': 'system' and 'allow': 'none' "
        "for non-admin users in rules.json"
    )
