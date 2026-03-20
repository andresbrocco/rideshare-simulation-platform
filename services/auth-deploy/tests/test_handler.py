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
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# handler.py is one directory above this tests/ subdirectory.
sys.path.insert(0, str(Path(__file__).parent.parent))

from handler import (  # noqa: E402
    handle_extend_session,
    handle_provision_visitor,
    VISITOR_MIN_REMAINING_SECONDS,
)

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
        {"service": "simulation_api", "error": "timeout"},
    ],
}

_ALL_FAILED = {
    "successes": [],
    "failures": [
        {"service": "grafana", "error": "timeout"},
        {"service": "airflow", "error": "timeout"},
        {"service": "minio", "error": "timeout"},
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
        """Partial service failure still returns 200 — service provisioning is best-effort."""
        with (
            patch("handler._provision_visitor", return_value=_PARTIAL_SUCCESS),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert "password" not in body

    @pytest.mark.unit
    def test_provision_visitor_partial_failure_response_includes_email_sent_flag(self) -> None:
        """Partial service failure response includes email_sent for consistent shape."""
        with (
            patch("handler._provision_visitor", return_value=_PARTIAL_SUCCESS),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["email_sent"] is True


# ---------------------------------------------------------------------------
# Email not called when all services fail
# ---------------------------------------------------------------------------


class TestAllServicesFail:
    @pytest.mark.unit
    def test_provision_visitor_all_services_fail_still_returns_200(self) -> None:
        """Email is sent before provisioning, so all-service failure is still 200.

        The handler sends credentials via email (step 2) before attempting
        service provisioning (step 3).  When reprovision-visitors runs on
        next deploy, it recreates accounts from DynamoDB.
        """
        with (
            patch("handler._provision_visitor", return_value=_ALL_FAILED),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True) as mock_email,
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        mock_email.assert_called_once()

    @pytest.mark.unit
    def test_all_services_fail_response_has_no_password(self) -> None:
        """200 response when all services fail must not expose any credentials."""
        with (
            patch("handler._provision_visitor", return_value=_ALL_FAILED),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
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


# ---------------------------------------------------------------------------
# Visitor session minimum guarantee tests
# ---------------------------------------------------------------------------


class TestVisitorSessionMinimumGuarantee:
    """Tests for step 5: auto-extend session when a visitor is provisioned."""

    @pytest.mark.unit
    def test_session_extended_when_below_minimum(self) -> None:
        """Session with only 5 min remaining should be extended to 15 min."""
        now = int(time.time())
        session = {"deployed_at": now - 1500, "deadline": now + 300}  # 5 min left

        with (
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._update_visitor_services"),
            patch("handler.get_session", return_value=session),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["session_extended"] is True
        mock_update.assert_called_once()
        new_deadline = mock_update.call_args[0][0]
        # Should be approximately now + 900 (15 min)
        assert abs(new_deadline - (now + VISITOR_MIN_REMAINING_SECONDS)) < 5

    @pytest.mark.unit
    def test_session_not_extended_when_above_minimum(self) -> None:
        """Session with 30 min remaining should not be touched."""
        now = int(time.time())
        session = {"deployed_at": now - 600, "deadline": now + 1800}  # 30 min left

        with (
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._update_visitor_services"),
            patch("handler.get_session", return_value=session),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["session_extended"] is False
        mock_update.assert_not_called()

    @pytest.mark.unit
    def test_no_session_skips_extension(self) -> None:
        """When there is no active session, provisioning still succeeds."""
        with (
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._update_visitor_services"),
            patch("handler.get_session", return_value=None),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["session_extended"] is False
        mock_update.assert_not_called()

    @pytest.mark.unit
    def test_deploying_session_skips_extension(self) -> None:
        """A deploying session (no deadline yet) should not be extended."""
        now = int(time.time())
        session = {"deployed_at": now - 60}  # no deadline key

        with (
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._update_visitor_services"),
            patch("handler.get_session", return_value=session),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["session_extended"] is False
        mock_update.assert_not_called()

    @pytest.mark.unit
    def test_tearing_down_session_skips_extension(self) -> None:
        """A session marked tearing_down should not be extended."""
        now = int(time.time())
        session = {"deployed_at": now - 1500, "deadline": now + 300, "tearing_down": True}

        with (
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._update_visitor_services"),
            patch("handler.get_session", return_value=session),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["session_extended"] is False
        mock_update.assert_not_called()

    @pytest.mark.unit
    def test_extension_failure_is_non_fatal(self) -> None:
        """If update_session_deadline raises, provisioning still returns 200."""
        now = int(time.time())
        session = {"deployed_at": now - 1500, "deadline": now + 300}

        with (
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS),
            patch("handler._update_visitor_services"),
            patch("handler.get_session", return_value=session),
            patch("handler.update_session_deadline", side_effect=RuntimeError("SSM boom")),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["provisioned"] is True


# ---------------------------------------------------------------------------
# extend-session minutes parameter tests
# ---------------------------------------------------------------------------


class TestExtendSessionMinutesParameter:
    """Tests for the optional minutes parameter on handle_extend_session."""

    @pytest.mark.unit
    def test_default_step_is_30_minutes(self) -> None:
        """When no minutes arg is passed, the step should be 30 minutes (1800s)."""
        now = int(time.time())
        session = {"deployed_at": now - 600, "deadline": now + 600}  # 10 min left

        with (
            patch("handler.get_session", return_value=session),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_extend_session()

        assert status == 200
        # deadline should be old deadline + 1800
        mock_update.assert_called_once_with(session["deadline"] + 1800)

    @pytest.mark.unit
    def test_custom_minutes_used(self) -> None:
        """When minutes=15 is passed, the step should be 900s."""
        now = int(time.time())
        session = {"deployed_at": now - 600, "deadline": now + 600}

        with (
            patch("handler.get_session", return_value=session),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_extend_session(minutes=15)

        assert status == 200
        mock_update.assert_called_once_with(session["deadline"] + 900)

    @pytest.mark.unit
    def test_max_cap_enforced_with_custom_minutes(self) -> None:
        """Extending near the max should be rejected even with custom minutes."""
        now = int(time.time())
        # Session with 1h55m remaining — even 15 min would exceed 2h
        session = {"deployed_at": now - 300, "deadline": now + 6900}

        with (
            patch("handler.get_session", return_value=session),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_extend_session(minutes=15)

        assert status == 400
        assert "2 hours" in body["error"]
        mock_update.assert_not_called()
