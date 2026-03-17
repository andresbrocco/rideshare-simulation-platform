"""Unit tests for the PBKDF2-SHA256 password hashing helper in handler.py.

Validates:
- Output format is parseable by Trino's file-based password authenticator
- Deterministic output for a known input with a fixed salt (regression guard)
- Salt randomness: two calls produce different hashes
- bcrypt is not referenced anywhere in _store_visitor_dynamodb

These tests are pure unit tests — no running services required.
"""

from __future__ import annotations

import hashlib
import inspect
import re
import sys
from pathlib import Path
from typing import Any

import pytest

# Load handler.py directly without triggering module-level AWS SDK calls.
# handler.py lives alongside this test file.
_HANDLER_PATH = Path(__file__).parent / "handler.py"

# We import handler lazily inside each test that needs it so that side-effects
# are isolated.  boto3 is available in the Lambda venv but we do NOT want
# network calls during tests, so we import handler at module level via a
# sys.path manipulation and rely on each test's responsibility to avoid
# calling anything that hits AWS.

sys.path.insert(0, str(_HANDLER_PATH.parent))
import handler  # noqa: E402  (import after sys.path manipulation is intentional)


# ---------------------------------------------------------------------------
# _hash_password_pbkdf2 tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_hash_password_pbkdf2_format() -> None:
    """Output must be parseable by Trino's file-based password authenticator.

    The Trino file authenticator expects: ``iterations:hex_salt:hex_hash``
    where iterations is a positive integer and both salt and hash are
    lowercase hexadecimal strings.
    """
    result = handler._hash_password_pbkdf2("testpassword123")

    parts = result.split(":")
    assert len(parts) == 3, f"Expected 3 colon-delimited parts, got: {result!r}"

    iterations_str, hex_salt, hex_hash = parts

    # Iterations must be a positive integer.
    assert (
        iterations_str.isdigit() and int(iterations_str) > 0
    ), f"First component must be a positive integer, got: {iterations_str!r}"

    # Salt and hash must be non-empty lowercase hex strings.
    hex_pattern = re.compile(r"^[0-9a-f]+$")
    assert hex_pattern.match(hex_salt), f"Salt must be lowercase hex, got: {hex_salt!r}"
    assert hex_pattern.match(hex_hash), f"Hash must be lowercase hex, got: {hex_hash!r}"

    # Salt should be 16 bytes (32 hex chars), hash 32 bytes (64 hex chars) for SHA-256.
    assert len(hex_salt) == 32, f"Expected 32-char hex salt, got length {len(hex_salt)}"
    assert len(hex_hash) == 64, f"Expected 64-char hex hash, got length {len(hex_hash)}"


@pytest.mark.unit
def test_hash_password_pbkdf2_deterministic_with_fixed_salt(monkeypatch: Any) -> None:
    """Helper must produce a predictable output when os.urandom is fixed.

    This is a regression guard: if the algorithm or iteration count changes,
    this test will catch it.  The expected value was derived once with
    os.urandom returning b'\\x00' * 16 and password 'hello'.
    """
    fixed_salt = b"\x00" * 16
    monkeypatch.setattr("os.urandom", lambda n: fixed_salt[:n])

    result = handler._hash_password_pbkdf2("hello")

    # Pre-computed: 65536 iterations, all-zero 16-byte salt, SHA-256
    expected = (
        "65536"
        ":00000000000000000000000000000000"
        ":0e335e221ae79f39405c97b9b81eae160c4bd3f72d7707e20409fd8790dd94af"
    )
    assert (
        result == expected
    ), f"Deterministic hash mismatch.\nExpected: {expected}\nActual:   {result}"


@pytest.mark.unit
def test_hash_password_pbkdf2_unique_salts() -> None:
    """Two calls with the same password must produce different hashes.

    Verifies that os.urandom is called each time (salt is not reused).
    """
    hash_a = handler._hash_password_pbkdf2("same_password")
    hash_b = handler._hash_password_pbkdf2("same_password")

    assert hash_a != hash_b, (
        "Two calls to _hash_password_pbkdf2 with the same password produced "
        "identical output, indicating the salt is not random."
    )


@pytest.mark.unit
def test_hash_password_pbkdf2_iteration_count() -> None:
    """PBKDF2 iteration count must be exactly 65536."""
    result = handler._hash_password_pbkdf2("anypassword")
    iterations_str = result.split(":")[0]
    assert iterations_str == "65536", f"Expected iteration count 65536, got {iterations_str!r}"


# ---------------------------------------------------------------------------
# Static bcrypt-removal guards
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_store_visitor_dynamodb_no_bcrypt_import() -> None:
    """_store_visitor_dynamodb must not reference bcrypt anywhere in its source."""
    source = inspect.getsource(handler._store_visitor_dynamodb)
    assert "bcrypt" not in source, (
        "_store_visitor_dynamodb still references 'bcrypt' in its source code. "
        "All bcrypt usage must be replaced with _hash_password_pbkdf2."
    )


@pytest.mark.unit
def test_handler_module_no_bcrypt_anywhere() -> None:
    """The entire handler module source must not contain any 'bcrypt' reference."""
    source = _HANDLER_PATH.read_text()
    assert "bcrypt" not in source, (
        "handler.py still contains the word 'bcrypt'. " "All references must be removed."
    )


# ---------------------------------------------------------------------------
# Hash correctness cross-check
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_hash_password_pbkdf2_matches_stdlib_directly(monkeypatch: Any) -> None:
    """Helper output must match a direct hashlib.pbkdf2_hmac call with the same inputs."""
    fixed_salt = b"\xde\xad\xbe\xef" * 4  # 16 bytes, not all-zero
    monkeypatch.setattr("os.urandom", lambda n: fixed_salt[:n])

    result = handler._hash_password_pbkdf2("crosscheck_password")

    # Recompute independently.
    digest = hashlib.pbkdf2_hmac("sha256", b"crosscheck_password", fixed_salt, 65536)
    expected = f"65536:{fixed_salt.hex()}:{digest.hex()}"
    assert result == expected, (
        f"Helper output does not match direct stdlib computation.\n"
        f"Expected: {expected}\nActual:   {result}"
    )
