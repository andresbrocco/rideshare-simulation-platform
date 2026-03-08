"""Unit tests for Trino authentication and access-control configuration files.

Validates rules.json schema and access control rules, and the structure of
password.db.template.  These tests are pure file-validation tests — they
require no running services.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

# Resolve paths relative to the repository root from the test file's location.
# test_trino_config.py lives at infrastructure/lambda/auth-deploy/
# Repository root is four levels up: auth-deploy -> lambda -> infrastructure -> repo-root
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_TRINO_ETC = _REPO_ROOT / "services" / "trino" / "etc"
_RULES_JSON = _TRINO_ETC / "rules.json"
_PASSWORD_DB_TEMPLATE = _TRINO_ETC / "password.db.template"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rules() -> dict[str, list[dict[str, str]]]:
    """Load and return the parsed rules.json contents."""
    return cast(dict[str, list[dict[str, str]]], json.loads(_RULES_JSON.read_text()))


@pytest.fixture(scope="module")
def password_db_template_lines() -> list[str]:
    """Return non-empty lines from password.db.template."""
    return [line for line in _PASSWORD_DB_TEMPLATE.read_text().splitlines() if line.strip()]


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


# ---------------------------------------------------------------------------
# password.db.template tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_password_db_template_has_admin(
    password_db_template_lines: list[str],
) -> None:
    """password.db.template must contain a line for the admin user."""
    admin_lines = [line for line in password_db_template_lines if line.startswith("admin:")]
    assert admin_lines, "Expected a line starting with 'admin:' in password.db.template"


@pytest.mark.unit
def test_password_db_template_has_visitor(
    password_db_template_lines: list[str],
) -> None:
    """password.db.template must contain a line for the visitor user."""
    visitor_lines = [line for line in password_db_template_lines if line.startswith("visitor:")]
    assert visitor_lines, "Expected a line starting with 'visitor:' in password.db.template"
