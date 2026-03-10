"""Regression tests for the SES email hard-failure and credential-hiding fixes.

These tests verify:
- Email failure returns HTTP 500 (credentials reach the visitor only via email)
- Successful 200 response body never includes the plaintext password
- Successful 207 response body never includes the plaintext password
- Email is not attempted when all service provisioning steps fail
- All previously-passing validation paths remain unaffected

These are pure unit tests — no AWS credentials or running services are required.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# handler.py is one directory above this tests/ subdirectory.
sys.path.insert(0, str(Path(__file__).parent.parent))

from handler import handle_provision_visitor  # noqa: E402

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_EMAIL = "visitor@example.com"
_PASSWORD = "SecurePass99!"
_NAME = "Test Visitor"

_FULL_SUCCESS = {
    "successes": [
        {"service": "grafana", "result": {"status": "created", "user_id": 1}},
        {"service": "airflow", "result": {"status": "created", "username": _EMAIL}},
        {"service": "minio", "result": {"status": "created", "email": _EMAIL}},
        {"service": "trino", "result": {"status": "stored", "email": _EMAIL}},
        {
            "service": "simulation_api",
            "result": {"email": _EMAIL, "role": "viewer", "status": "created"},
        },
    ],
    "failures": [],
}

_PARTIAL_SUCCESS = {
    "successes": [
        {"service": "grafana", "result": {"status": "created", "user_id": 1}},
    ],
    "failures": [
        {"service": "airflow", "error": "Connection refused"},
        {"service": "minio", "error": "timeout"},
        {"service": "trino", "error": "timeout"},
        {"service": "simulation_api", "error": "timeout"},
    ],
}

_ALL_FAILED = {
    "successes": [],
    "failures": [
        {"service": "grafana", "error": "timeout"},
        {"service": "airflow", "error": "timeout"},
        {"service": "minio", "error": "timeout"},
        {"service": "trino", "error": "timeout"},
        {"service": "simulation_api", "error": "timeout"},
    ],
}


# ---------------------------------------------------------------------------
# Email hard-failure regression tests
# ---------------------------------------------------------------------------


class TestEmailFailureReturns500:
    @pytest.mark.unit
    def test_provision_visitor_email_failure_returns_500(self) -> None:
        """SES failure after successful provisioning must return 500.

        The visitor cannot retrieve their credentials without the welcome
        email, so the entire request must fail so they can retry.
        """
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=False),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 500
        assert "error" in body
        assert "password" not in body

    @pytest.mark.unit
    def test_email_failure_response_body_has_no_password(self) -> None:
        """500 response on email failure must never expose the plaintext password."""
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=False),
        ):
            _, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert "password" not in body

    @pytest.mark.unit
    def test_email_failure_with_partial_provisioning_returns_500(self) -> None:
        """SES failure after partial provisioning must also return 500.

        Even when some services succeeded, if the email cannot be sent the
        visitor has no way to learn their credentials.
        """
        with (
            patch("handler._provision_visitor", return_value=_PARTIAL_SUCCESS),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=False),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 500
        assert "error" in body
        assert "password" not in body


# ---------------------------------------------------------------------------
# Success response credential-hiding regression tests
# ---------------------------------------------------------------------------


class TestSuccessResponseHasNoPassword:
    @pytest.mark.unit
    def test_provision_visitor_success_response_has_no_password(self) -> None:
        """HTTP 200 response body must not contain the plaintext password.

        Credentials are delivered exclusively via the SES welcome email.
        """
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert "password" not in body

    @pytest.mark.unit
    def test_provision_visitor_success_response_includes_email_sent_flag(self) -> None:
        """HTTP 200 response body includes email_sent for consistent shape."""
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["email_sent"] is True

    @pytest.mark.unit
    def test_provision_visitor_partial_failure_response_has_no_password(self) -> None:
        """HTTP 207 response body must not contain the plaintext password."""
        with (
            patch("handler._provision_visitor", return_value=_PARTIAL_SUCCESS),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 207
        assert "password" not in body

    @pytest.mark.unit
    def test_provision_visitor_partial_failure_response_includes_email_sent_flag(self) -> None:
        """HTTP 207 response body includes email_sent for consistent shape."""
        with (
            patch("handler._provision_visitor", return_value=_PARTIAL_SUCCESS),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 207
        assert body["email_sent"] is True


# ---------------------------------------------------------------------------
# Email not called when all services fail
# ---------------------------------------------------------------------------


class TestEmailNotSentWhenAllServicesFail:
    @pytest.mark.unit
    def test_provision_visitor_all_services_fail_before_email(self) -> None:
        """Email must not be attempted when every provisioning step failed.

        There is nothing meaningful to tell the visitor via email if no
        account was created on any service.
        """
        with (
            patch("handler._provision_visitor", return_value=_ALL_FAILED),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email") as mock_email,
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 500
        assert "error" in body
        mock_email.assert_not_called()

    @pytest.mark.unit
    def test_all_services_fail_response_has_no_password(self) -> None:
        """500 response when all services fail must not expose any credentials."""
        with (
            patch("handler._provision_visitor", return_value=_ALL_FAILED),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email"),
        ):
            _, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert "password" not in body


# ---------------------------------------------------------------------------
# Validation paths unaffected
# ---------------------------------------------------------------------------


class TestValidationPathsUnaffected:
    @pytest.mark.unit
    def test_missing_email_returns_400(self) -> None:
        """400 validation path for missing email must be unaffected by the email fix."""
        status, body = handle_provision_visitor("", _PASSWORD, _NAME)

        assert status == 400
        assert "error" in body
        assert "password" not in body

    @pytest.mark.unit
    def test_short_password_returns_400(self) -> None:
        """400 validation path for short explicit password must be unaffected."""
        status, body = handle_provision_visitor(_EMAIL, "short", _NAME)

        assert status == 400
        assert "error" in body
        assert "password" not in body
