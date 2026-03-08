"""Unit tests for the user store module."""

import pytest

import src.api.user_store as user_store_module
from src.api.user_store import UserStore, get_user_store


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Reset the module-level singleton before each test to prevent cross-test pollution."""
    user_store_module._user_store = None
    yield
    user_store_module._user_store = None


@pytest.mark.unit
def test_add_and_get_user() -> None:
    """Round-trip: add a user then retrieve it by email."""
    store = UserStore()
    store.add_user("a@b.com", "pass", "viewer")
    record = store.get_user("a@b.com")
    assert record is not None
    assert record.email == "a@b.com"
    assert record.role == "viewer"
    # Stored hash must differ from the plaintext password
    assert record.hashed_password != "pass"


@pytest.mark.unit
def test_get_user_missing() -> None:
    """Looking up an unknown email returns None."""
    store = UserStore()
    assert store.get_user("unknown@b.com") is None


@pytest.mark.unit
def test_verify_password_correct() -> None:
    """Correct password returns the matching UserRecord."""
    store = UserStore()
    store.add_user("a@b.com", "pass", "viewer")
    record = store.verify_password("a@b.com", "pass")
    assert record is not None
    assert record.role == "viewer"


@pytest.mark.unit
def test_verify_password_wrong() -> None:
    """Wrong password returns None."""
    store = UserStore()
    store.add_user("a@b.com", "pass", "viewer")
    assert store.verify_password("a@b.com", "wrong") is None


@pytest.mark.unit
def test_verify_password_unknown_email() -> None:
    """Unknown email returns None regardless of the supplied password."""
    store = UserStore()
    assert store.verify_password("nobody@b.com", "pass") is None


@pytest.mark.unit
def test_password_is_hashed() -> None:
    """Stored hashed_password is a bcrypt hash, not the plaintext secret."""
    store = UserStore()
    record = store.add_user("a@b.com", "secret", "admin")
    assert record.hashed_password != "secret"
    # bcrypt hashes always start with the $2b$ prefix
    assert record.hashed_password.startswith("$2b$")


@pytest.mark.unit
def test_admin_role_stored() -> None:
    """Admin role is preserved through the round-trip."""
    store = UserStore()
    record = store.add_user("admin@b.com", "pw", "admin")
    assert record.role == "admin"


@pytest.mark.unit
def test_singleton_returns_same_instance() -> None:
    """get_user_store() returns the same object on consecutive calls."""
    first = get_user_store()
    second = get_user_store()
    assert first is second
