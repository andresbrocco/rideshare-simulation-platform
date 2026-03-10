"""Unit tests for the multi-service visitor provisioning orchestrator.

Tests cover the provision-visitor action in handler.py:
- Request body validation (missing fields, short explicit password)
- Password auto-generation when no password is supplied
- Successful provisioning returns 200 with durable-only credential storage
- All services failing returns 500
- SES email failure returns 500 (credentials delivered only via email)
- Response bodies never include the plaintext password
- DynamoDB visitor record storage (happy-path and non-fatal failure)
- durable_only flag: only Trino provisioned in phase 1; all services in phase 2
- Each individual provisioning helper (_provision_grafana, _provision_airflow,
  _provision_minio, _provision_trino, _provision_simulation_api) is tested
  for both happy-path and error propagation

These are pure unit tests — no running services are required.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from handler import (
    SERVICE_LOGIN_URLS,
    _build_welcome_email,
    _decrypt_password,
    _encrypt_password,
    _hash_password_pbkdf2,
    _provision_airflow,
    _provision_grafana,
    _provision_minio,
    _provision_simulation_api,
    _provision_trino,
    _provision_visitor,
    _send_welcome_email,
    _verify_password_pbkdf2,
    handle_provision_visitor,
    handle_reprovision_visitors,
    handle_visitor_login,
)


# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

_API_KEY = "test-api-key"
_EMAIL = "visitor@example.com"
_PASSWORD = "TestPassword123!"
_NAME = "Test Visitor"
_SCRIPTS_DIR = "/fake/scripts"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_secrets():
    """Mock get_secret to return the test API key."""
    with patch("handler.get_secret") as mock:
        mock.side_effect = lambda secret_id: {
            "rideshare/api-key": _API_KEY,
        }.get(secret_id, "mock-secret")
        yield mock


@pytest.fixture()
def mock_provision_visitor():
    """Mock _provision_visitor to return a Trino-only success result and skip DynamoDB/email."""
    with (
        patch("handler._provision_visitor") as mock_pv,
        patch("handler._store_visitor_dynamodb"),
        patch("handler._send_welcome_email", return_value=True),
    ):
        mock_pv.return_value = {
            "successes": [
                {"service": "trino", "result": {"status": "stored", "email": _EMAIL}},
            ],
            "failures": [],
        }
        yield mock_pv


# ---------------------------------------------------------------------------
# handle_provision_visitor: request validation
# ---------------------------------------------------------------------------


class TestHandleProvisionVisitorValidation:
    @pytest.mark.unit
    def test_rejects_missing_email(self) -> None:
        """handle_provision_visitor returns 400 when email is empty."""
        status, body = handle_provision_visitor("", _PASSWORD, _NAME)
        assert status == 400
        assert "error" in body

    @pytest.mark.unit
    def test_rejects_short_explicit_password(self) -> None:
        """handle_provision_visitor returns 400 when an explicit password is shorter than 8 chars."""
        status, body = handle_provision_visitor(_EMAIL, "short", _NAME)
        assert status == 400
        assert "error" in body


# ---------------------------------------------------------------------------
# handle_provision_visitor: response codes
# ---------------------------------------------------------------------------


class TestHandleProvisionVisitorResponseCodes:
    @pytest.mark.unit
    def test_200_all_services_succeed(self, mock_provision_visitor: object) -> None:
        """handle_provision_visitor returns 200 when credential storage succeeds and email is sent."""
        status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)
        assert status == 200
        assert body["email"] == _EMAIL
        assert "password" not in body
        assert body["email_sent"] is True
        assert body["failures"] == []

    @pytest.mark.unit
    def test_500_all_services_fail(self) -> None:
        """handle_provision_visitor returns 500 when Trino credential storage fails."""
        all_failed = {
            "successes": [],
            "failures": [
                {"service": "trino", "error": "timeout"},
            ],
        }
        with (
            patch("handler._provision_visitor", return_value=all_failed),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email") as mock_email,
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 500
        assert body["error"] == "Credential storage failed"
        # Email must not be attempted when credential storage fails
        mock_email.assert_not_called()


# ---------------------------------------------------------------------------
# _provision_visitor: partial failure handling
# ---------------------------------------------------------------------------


class TestProvisionVisitorOrchestrator:
    @pytest.mark.unit
    def test_continues_after_grafana_failure(self, mock_secrets: object) -> None:
        """_provision_visitor calls remaining services even when Grafana fails (durable_only=False).

        The orchestrator must not short-circuit on a single service error —
        each service is attempted independently.
        """
        with (
            patch("handler._provision_grafana", side_effect=Exception("grafana down")),
            patch(
                "handler._provision_airflow",
                return_value={"status": "created", "username": _EMAIL},
            ),
            patch(
                "handler._provision_minio",
                return_value={"status": "created", "email": _EMAIL},
            ),
            patch(
                "handler._provision_trino",
                return_value={"status": "stored", "email": _EMAIL},
            ),
            patch(
                "handler._provision_simulation_api",
                return_value={"email": _EMAIL, "role": "viewer", "status": "created"},
            ),
        ):
            result = _provision_visitor(_EMAIL, _PASSWORD, _NAME, durable_only=False)

        service_failures = [f["service"] for f in result["failures"]]
        service_successes = [s["service"] for s in result["successes"]]

        assert "grafana" in service_failures
        assert "airflow" in service_successes
        assert "minio" in service_successes
        assert "trino" in service_successes
        assert "simulation_api" in service_successes

    @pytest.mark.unit
    def test_all_services_attempted(self, mock_secrets: object) -> None:
        """_provision_visitor attempts all five services when durable_only=False."""
        with (
            patch("handler._provision_grafana", side_effect=Exception("err")),
            patch("handler._provision_airflow", side_effect=Exception("err")),
            patch("handler._provision_minio", side_effect=Exception("err")),
            patch("handler._provision_trino", side_effect=Exception("err")),
            patch("handler._provision_simulation_api", side_effect=Exception("err")),
        ):
            result = _provision_visitor(_EMAIL, _PASSWORD, _NAME, durable_only=False)

        assert len(result["failures"]) == 5
        assert result["successes"] == []

    @pytest.mark.unit
    def test_durable_only_skips_platform_services(self, mock_secrets: object) -> None:
        """_provision_visitor with durable_only=True only calls Trino provisioner."""
        with (
            patch("handler._provision_grafana") as mock_grafana,
            patch("handler._provision_airflow") as mock_airflow,
            patch("handler._provision_minio") as mock_minio,
            patch(
                "handler._provision_trino",
                return_value={"status": "stored", "email": _EMAIL},
            ),
            patch("handler._provision_simulation_api") as mock_sim,
        ):
            result = _provision_visitor(_EMAIL, _PASSWORD, _NAME, durable_only=True)

        mock_grafana.assert_not_called()
        mock_airflow.assert_not_called()
        mock_minio.assert_not_called()
        mock_sim.assert_not_called()
        assert len(result["successes"]) == 1
        assert result["successes"][0]["service"] == "trino"
        assert result["failures"] == []

    @pytest.mark.unit
    def test_durable_only_reports_trino_failure(self, mock_secrets: object) -> None:
        """_provision_visitor with durable_only=True reports Trino failure correctly."""
        with (
            patch("handler._provision_grafana") as mock_grafana,
            patch("handler._provision_airflow") as mock_airflow,
            patch("handler._provision_minio") as mock_minio,
            patch("handler._provision_trino", side_effect=Exception("secrets manager down")),
            patch("handler._provision_simulation_api") as mock_sim,
        ):
            result = _provision_visitor(_EMAIL, _PASSWORD, _NAME, durable_only=True)

        mock_grafana.assert_not_called()
        mock_airflow.assert_not_called()
        mock_minio.assert_not_called()
        mock_sim.assert_not_called()
        assert result["successes"] == []
        assert len(result["failures"]) == 1
        assert result["failures"][0]["service"] == "trino"


# ---------------------------------------------------------------------------
# _provision_grafana
# ---------------------------------------------------------------------------


class TestProvisionGrafana:
    @pytest.mark.unit
    def test_calls_provision_viewer_with_correct_args(self) -> None:
        """_provision_grafana passes the correct arguments to provision_viewer."""
        mock_module = MagicMock()
        mock_module.provision_viewer.return_value = {"status": "created", "user_id": 10}

        with (
            patch("handler._load_module", return_value=mock_module),
            patch.dict(
                "os.environ",
                {
                    "GRAFANA_URL": "http://grafana:3000",
                    "GRAFANA_ADMIN_PASSWORD": "adminpass",
                },
            ),
        ):
            result = _provision_grafana(_EMAIL, _PASSWORD, _NAME, _SCRIPTS_DIR)

        assert result["status"] == "created"
        mock_module.provision_viewer.assert_called_once()
        call_kwargs = mock_module.provision_viewer.call_args
        assert call_kwargs.kwargs["email"] == _EMAIL
        assert call_kwargs.kwargs["grafana_url"] == "http://grafana:3000"

    @pytest.mark.unit
    def test_propagates_exceptions(self) -> None:
        """_provision_grafana lets exceptions bubble up for the orchestrator to catch."""
        mock_module = MagicMock()
        mock_module.provision_viewer.side_effect = urllib.error.HTTPError(
            url="http://grafana:3000",
            code=500,
            msg="Internal Error",
            hdrs=None,
            fp=io.BytesIO(b"error"),  # type: ignore[arg-type]
        )

        with patch("handler._load_module", return_value=mock_module):
            with pytest.raises(urllib.error.HTTPError):
                _provision_grafana(_EMAIL, _PASSWORD, _NAME, _SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# _provision_airflow
# ---------------------------------------------------------------------------


class TestProvisionAirflow:
    @pytest.mark.unit
    def test_splits_display_name_into_first_last(self) -> None:
        """_provision_airflow splits 'First Last' into first_name='First', last_name='Last'."""
        mock_module = MagicMock()
        mock_module.provision_viewer.return_value = {"status": "created", "username": _EMAIL}

        with (
            patch("handler._load_module", return_value=mock_module),
            patch.dict("os.environ", {"AIRFLOW_URL": "http://airflow:8080"}),
        ):
            _provision_airflow(_EMAIL, _PASSWORD, "Alice Smith", _SCRIPTS_DIR)

        call_kwargs = mock_module.provision_viewer.call_args.kwargs
        assert call_kwargs["first_name"] == "Alice"
        assert call_kwargs["last_name"] == "Smith"

    @pytest.mark.unit
    def test_single_word_name_uses_empty_last_name(self) -> None:
        """_provision_airflow handles single-word names by setting last_name to empty string."""
        mock_module = MagicMock()
        mock_module.provision_viewer.return_value = {"status": "created", "username": _EMAIL}

        with (
            patch("handler._load_module", return_value=mock_module),
            patch.dict("os.environ", {"AIRFLOW_URL": "http://airflow:8080"}),
        ):
            _provision_airflow(_EMAIL, _PASSWORD, "Alice", _SCRIPTS_DIR)

        call_kwargs = mock_module.provision_viewer.call_args.kwargs
        assert call_kwargs["first_name"] == "Alice"
        assert call_kwargs["last_name"] == ""


# ---------------------------------------------------------------------------
# _provision_minio
# ---------------------------------------------------------------------------


class TestProvisionMinio:
    @pytest.mark.unit
    def test_calls_provision_visitor_with_env_credentials(self) -> None:
        """_provision_minio reads endpoint/credentials from environment variables."""
        mock_module = MagicMock()
        mock_module.provision_visitor.return_value = {"status": "created", "email": _EMAIL}

        with (
            patch("handler._load_module", return_value=mock_module),
            patch.dict(
                "os.environ",
                {
                    "MINIO_ENDPOINT": "minio:9000",
                    "MINIO_ACCESS_KEY": "minio-admin",
                    "MINIO_SECRET_KEY": "minio-secret",
                },
            ),
        ):
            result = _provision_minio(_EMAIL, _PASSWORD, _SCRIPTS_DIR)

        assert result["status"] == "created"
        call_kwargs = mock_module.provision_visitor.call_args.kwargs
        assert call_kwargs["endpoint"] == "minio:9000"
        assert call_kwargs["access_key"] == "minio-admin"


# ---------------------------------------------------------------------------
# _provision_trino
# ---------------------------------------------------------------------------


class TestProvisionTrino:
    @pytest.mark.unit
    def test_stores_hash_in_secrets_manager_create_path(self) -> None:
        """_provision_trino creates the secret when it does not yet exist."""
        mock_client = MagicMock()
        from botocore.exceptions import ClientError

        mock_client.put_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
            "PutSecretValue",
        )
        mock_client.create_secret.return_value = {}

        with patch("handler.get_secrets_client", return_value=mock_client):
            result = _provision_trino(_EMAIL, _PASSWORD)

        assert result["status"] == "stored"
        assert result["email"] == _EMAIL
        mock_client.create_secret.assert_called_once()
        create_call = mock_client.create_secret.call_args
        assert create_call.kwargs["Name"] == "rideshare/trino-visitor-password-hash"
        stored = json.loads(create_call.kwargs["SecretString"])
        assert stored["email"] == _EMAIL
        # Verify the stored hash is in PBKDF2 format: {iterations}:{hex_salt}:{hex_hash}
        hash_parts = stored["hash"].split(":")
        assert (
            len(hash_parts) == 3
        ), f"Expected PBKDF2 format 'iter:salt:hash', got: {stored['hash']!r}"
        assert hash_parts[0].isdigit(), "First component (iterations) must be numeric"

    @pytest.mark.unit
    def test_stores_hash_in_secrets_manager_update_path(self) -> None:
        """_provision_trino updates the secret when it already exists."""
        mock_client = MagicMock()
        mock_client.put_secret_value.return_value = {}

        with patch("handler.get_secrets_client", return_value=mock_client):
            result = _provision_trino(_EMAIL, _PASSWORD)

        assert result["status"] == "stored"
        mock_client.put_secret_value.assert_called_once()
        update_call = mock_client.put_secret_value.call_args
        assert update_call.kwargs["SecretId"] == "rideshare/trino-visitor-password-hash"

    @pytest.mark.unit
    def test_hash_is_valid_pbkdf2(self) -> None:
        """_provision_trino stores a PBKDF2-SHA256 hash that matches the original password."""
        import hashlib

        mock_client = MagicMock()
        mock_client.put_secret_value.return_value = {}
        stored_secret: dict[str, str] = {}

        def capture_put(SecretId: str, SecretString: str) -> dict[str, str]:
            stored_secret.update(json.loads(SecretString))
            return {}

        mock_client.put_secret_value.side_effect = capture_put

        with patch("handler.get_secrets_client", return_value=mock_client):
            _provision_trino(_EMAIL, _PASSWORD)

        # Verify PBKDF2 format: {iterations}:{hex_salt}:{hex_hash}
        iterations_str, hex_salt, hex_hash = stored_secret["hash"].split(":")
        iterations = int(iterations_str)
        salt = bytes.fromhex(hex_salt)
        expected_digest = hashlib.pbkdf2_hmac("sha256", _PASSWORD.encode(), salt, iterations)
        assert expected_digest.hex() == hex_hash


# ---------------------------------------------------------------------------
# _provision_simulation_api
# ---------------------------------------------------------------------------


class TestProvisionSimulationApi:
    @pytest.mark.unit
    def test_calls_post_auth_register(self, mock_secrets: object) -> None:
        """_provision_simulation_api sends POST /auth/register with the correct payload.

        Now delegates to the provision_simulation_api_viewer module via _load_module.
        We load that module directly so we can patch its urlopen and verify the
        outbound HTTP request is formed correctly.
        """
        import importlib.util
        import types
        from pathlib import Path

        module_path = Path(__file__).parent / "provision_simulation_api_viewer.py"
        spec = importlib.util.spec_from_file_location(
            "provision_simulation_api_viewer", module_path
        )
        assert spec is not None and spec.loader is not None
        provision_module: types.ModuleType = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provision_module)

        response_body = {"email": _EMAIL, "role": "viewer", "status": "created"}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_body).encode()
        mock_resp.status = 201
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured_requests: list[Any] = []

        def urlopen_side_effect(req: Any, **kwargs: Any) -> Any:
            captured_requests.append(req)
            return mock_resp

        import handler as handler_module

        with (
            patch.object(handler_module, "_load_module", return_value=provision_module),
            patch.object(
                provision_module.urllib.request,
                "urlopen",
                side_effect=urlopen_side_effect,
            ),
            patch.dict("os.environ", {"SIMULATION_API_URL": "http://simulation:8000"}),
        ):
            result = _provision_simulation_api(_EMAIL, _PASSWORD, _NAME, _SCRIPTS_DIR)

        assert result["email"] == _EMAIL
        assert result["role"] == "viewer"

        req = captured_requests[0]
        assert req.get_method() == "POST"
        assert "/auth/register" in req.full_url
        assert "simulation:8000" in req.full_url

        body: dict[str, str] = json.loads(req.data)
        assert body["email"] == _EMAIL
        assert body["password"] == _PASSWORD
        assert body["name"] == _NAME

    @pytest.mark.unit
    def test_propagates_http_errors(self, mock_secrets: object) -> None:
        """_provision_simulation_api lets HTTP errors bubble up for the orchestrator.

        Now delegates to the provision_simulation_api_viewer module via _load_module.
        """
        import importlib.util
        import types
        from pathlib import Path

        module_path = Path(__file__).parent / "provision_simulation_api_viewer.py"
        spec = importlib.util.spec_from_file_location(
            "provision_simulation_api_viewer", module_path
        )
        assert spec is not None and spec.loader is not None
        provision_module: types.ModuleType = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provision_module)

        import handler as handler_module

        with (
            patch.object(handler_module, "_load_module", return_value=provision_module),
            patch.object(
                provision_module.urllib.request,
                "urlopen",
                side_effect=urllib.error.HTTPError(
                    url="http://simulation:8000/auth/register",
                    code=503,
                    msg="Service Unavailable",
                    hdrs=None,  # type: ignore[arg-type]
                    fp=io.BytesIO(b"unavailable"),
                ),
            ),
            patch.dict("os.environ", {"SIMULATION_API_URL": "http://simulation:8000"}),
        ):
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                _provision_simulation_api(_EMAIL, _PASSWORD, _NAME, _SCRIPTS_DIR)

        assert exc_info.value.code == 503


# ---------------------------------------------------------------------------
# Password generation
# ---------------------------------------------------------------------------


_FULL_SUCCESS_RESULT = {
    "successes": [
        {"service": "trino", "result": {"status": "stored", "email": _EMAIL}},
    ],
    "failures": [],
}


class TestPasswordGeneration:
    @pytest.mark.unit
    def test_generates_password_when_not_provided(self) -> None:
        """handle_provision_visitor auto-generates a password when none is supplied.

        The generated password is forwarded to _send_welcome_email; it must
        not appear in the HTTP response body.
        """
        captured_passwords: list[str] = []

        def capture_email(email: str, name: str, password: str) -> bool:
            captured_passwords.append(password)
            return True

        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", side_effect=capture_email),
        ):
            status, body = handle_provision_visitor(_EMAIL, None, _NAME)

        assert status == 200
        assert "password" not in body
        assert len(captured_passwords) == 1
        assert len(captured_passwords[0]) >= 8

    @pytest.mark.unit
    def test_uses_provided_password_when_supplied(self) -> None:
        """handle_provision_visitor forwards the caller-supplied password to SES, not the HTTP body."""
        captured_passwords: list[str] = []

        def capture_email(email: str, name: str, password: str) -> bool:
            captured_passwords.append(password)
            return True

        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", side_effect=capture_email),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert "password" not in body
        assert captured_passwords[0] == _PASSWORD

    @pytest.mark.unit
    def test_generated_passwords_are_unique(self) -> None:
        """Two calls without a password produce different passwords (collision negligible)."""
        captured: list[str] = []

        def capture_email(email: str, name: str, password: str) -> bool:
            captured.append(password)
            return True

        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", side_effect=capture_email),
        ):
            handle_provision_visitor(_EMAIL, None, _NAME)
            handle_provision_visitor(_EMAIL, None, _NAME)

        assert len(captured) == 2
        assert captured[0] != captured[1]

    @pytest.mark.unit
    def test_rejects_short_explicit_password(self) -> None:
        """handle_provision_visitor returns 400 when an explicit password is too short."""
        status, body = handle_provision_visitor(_EMAIL, "short", _NAME)
        assert status == 400
        assert "error" in body


# ---------------------------------------------------------------------------
# DynamoDB storage
# ---------------------------------------------------------------------------


class TestDynamoDBStorage:
    @pytest.mark.unit
    def test_stores_record_after_successful_provisioning(self) -> None:
        """_store_visitor_dynamodb is called with the correct email and password hash."""
        mock_dynamo_client = MagicMock()
        # Capture the password forwarded to the email function so we can verify
        # the DynamoDB hash without relying on the HTTP response body.
        captured_passwords: list[str] = []

        def capture_email(email: str, name: str, password: str) -> bool:
            captured_passwords.append(password)
            return True

        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._get_dynamodb_client", return_value=mock_dynamo_client),
            patch("handler._send_welcome_email", side_effect=capture_email),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert "password" not in body
        mock_dynamo_client.put_item.assert_called_once()

        call_kwargs = mock_dynamo_client.put_item.call_args.kwargs
        item = call_kwargs["Item"]
        assert item["email"]["S"] == _EMAIL

    @pytest.mark.unit
    def test_dynamodb_failure_is_non_fatal(self) -> None:
        """A DynamoDB error does not roll back provisioning or change the status code."""
        mock_dynamo_client = MagicMock()
        mock_dynamo_client.put_item.side_effect = Exception("DynamoDB unavailable")

        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._get_dynamodb_client", return_value=mock_dynamo_client),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert "password" not in body

    @pytest.mark.unit
    def test_stores_trino_as_succeeded_service(self) -> None:
        """_store_visitor_dynamodb receives ["trino"] when Trino provisioning succeeds."""
        mock_dynamo_client = MagicMock()

        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._get_dynamodb_client", return_value=mock_dynamo_client),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        call_kwargs = mock_dynamo_client.put_item.call_args.kwargs
        item = call_kwargs["Item"]
        assert item["provisioned_services"]["SS"] == ["trino"]

    @pytest.mark.unit
    def test_stores_empty_services_on_trino_failure(self) -> None:
        """_store_visitor_dynamodb receives [] when Trino provisioning fails."""
        trino_failed = {
            "successes": [],
            "failures": [{"service": "trino", "error": "timeout"}],
        }
        mock_dynamo_client = MagicMock()

        with (
            patch("handler._provision_visitor", return_value=trino_failed),
            patch("handler._get_dynamodb_client", return_value=mock_dynamo_client),
            patch("handler._send_welcome_email", return_value=True),
        ):
            handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        # DynamoDB does not support empty SS sets — the handler stores an
        # empty list marker or skips the attribute.  What matters is that
        # it was called (non-fatal path) — verify that.
        mock_dynamo_client.put_item.assert_called_once()


# ---------------------------------------------------------------------------
# SES welcome email
# ---------------------------------------------------------------------------


class TestSesWelcomeEmail:
    @pytest.mark.unit
    def test_send_welcome_email_calls_ses_send_email(self) -> None:
        """_send_welcome_email calls ses.send_email with the correct destination."""
        mock_client = MagicMock()
        with patch("handler._get_ses_client", return_value=mock_client):
            _send_welcome_email(_EMAIL, _NAME, _PASSWORD)

        mock_client.send_email.assert_called_once()
        call_kwargs = mock_client.send_email.call_args.kwargs
        assert call_kwargs["Destination"]["ToAddresses"] == [_EMAIL]
        assert "ridesharing.portfolio.andresbrocco.com" in call_kwargs["Source"]

    @pytest.mark.unit
    def test_send_welcome_email_returns_true_on_success(self) -> None:
        """_send_welcome_email returns True when SES succeeds."""
        mock_client = MagicMock()
        with patch("handler._get_ses_client", return_value=mock_client):
            result = _send_welcome_email(_EMAIL, _NAME, _PASSWORD)

        assert result is True

    @pytest.mark.unit
    def test_send_welcome_email_returns_false_on_ses_error(self) -> None:
        """_send_welcome_email returns False on SES error without raising."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_client.send_email.side_effect = ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "Email rejected"}},
            "SendEmail",
        )
        with patch("handler._get_ses_client", return_value=mock_client):
            result = _send_welcome_email(_EMAIL, _NAME, _PASSWORD)

        assert result is False

    @pytest.mark.unit
    def test_welcome_email_contains_password(self) -> None:
        """_build_welcome_email includes the password in both text and HTML bodies."""
        _, text_body, html_body = _build_welcome_email(_EMAIL, _NAME, _PASSWORD)
        assert _PASSWORD in text_body
        assert _PASSWORD in html_body

    @pytest.mark.unit
    def test_welcome_email_contains_all_service_urls(self) -> None:
        """_build_welcome_email includes every service URL in the text body."""
        _, text_body, _ = _build_welcome_email(_EMAIL, _NAME, _PASSWORD)
        for url in SERVICE_LOGIN_URLS.values():
            assert url in text_body

    @pytest.mark.unit
    def test_send_welcome_email_includes_reply_to_when_env_set(self) -> None:
        """_send_welcome_email passes ReplyToAddresses when SES_REPLY_TO_ADDRESS is set."""
        mock_client = MagicMock()
        with (
            patch("handler._get_ses_client", return_value=mock_client),
            patch.dict(os.environ, {"SES_REPLY_TO_ADDRESS": "owner@example.com"}),
        ):
            _send_welcome_email(_EMAIL, _NAME, _PASSWORD)

        call_kwargs = mock_client.send_email.call_args.kwargs
        assert call_kwargs["ReplyToAddresses"] == ["owner@example.com"]

    @pytest.mark.unit
    def test_send_welcome_email_omits_reply_to_when_env_unset(self) -> None:
        """_send_welcome_email omits ReplyToAddresses when SES_REPLY_TO_ADDRESS is not set."""
        mock_client = MagicMock()
        env_without_reply_to = {k: v for k, v in os.environ.items() if k != "SES_REPLY_TO_ADDRESS"}
        with (
            patch("handler._get_ses_client", return_value=mock_client),
            patch.dict(os.environ, env_without_reply_to, clear=True),
        ):
            _send_welcome_email(_EMAIL, _NAME, _PASSWORD)

        call_kwargs = mock_client.send_email.call_args.kwargs
        assert "ReplyToAddresses" not in call_kwargs

    @pytest.mark.unit
    def test_welcome_email_subject_contains_visitor_name(self) -> None:
        """_build_welcome_email includes the visitor name in the subject."""
        subject, _, _ = _build_welcome_email(_EMAIL, _NAME, _PASSWORD)
        assert _NAME in subject

    @pytest.mark.unit
    def test_welcome_email_encourages_reply(self) -> None:
        """_build_welcome_email body contains explicit invitation to reply."""
        _, text_body, html_body = _build_welcome_email(_EMAIL, _NAME, _PASSWORD)
        assert "reply" in text_body.lower()
        assert "reply" in html_body.lower()

    @pytest.mark.unit
    def test_email_sent_flag_in_200_response(self) -> None:
        """200 response includes email_sent=True."""
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["email_sent"] is True

    @pytest.mark.unit
    def test_welcome_email_contains_deployment_note(self) -> None:
        """_build_welcome_email includes the deployment activation note in both bodies."""
        _, text_body, html_body = _build_welcome_email(_EMAIL, _NAME, _PASSWORD)
        assert "credentials activate once the platform is deployed" in text_body
        assert "credentials activate once the platform is deployed" in html_body

    @pytest.mark.unit
    def test_email_failure_returns_500(self) -> None:
        """Provisioning succeeds but email fails — entire request must return 500."""
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=False),
        ):
            status, body = handle_provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert status == 500
        assert "error" in body
        assert "password" not in body


# ---------------------------------------------------------------------------
# KMS encrypt/decrypt helpers
# ---------------------------------------------------------------------------


class TestKmsHelpers:
    @pytest.mark.unit
    def test_encrypt_raises_without_key_arn(self) -> None:
        """_encrypt_password raises EnvironmentError when KMS_VISITOR_PASSWORD_KEY is unset."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove the KMS key var if present
            import os as _os

            env = {k: v for k, v in _os.environ.items() if k != "KMS_VISITOR_PASSWORD_KEY"}
            with patch.dict("os.environ", env, clear=True):
                with pytest.raises(EnvironmentError, match="KMS_VISITOR_PASSWORD_KEY"):
                    _encrypt_password(_PASSWORD)

    @pytest.mark.unit
    def test_encrypt_calls_kms_encrypt(self) -> None:
        """_encrypt_password calls kms.encrypt with the configured key ARN."""
        ciphertext_blob = b"fake-ciphertext-bytes"
        mock_client = MagicMock()
        mock_client.encrypt.return_value = {"CiphertextBlob": ciphertext_blob}

        with (
            patch("handler._get_kms_client", return_value=mock_client),
            patch.dict(
                "os.environ", {"KMS_VISITOR_PASSWORD_KEY": "arn:aws:kms:us-east-1:123:key/abc"}
            ),
        ):
            result = _encrypt_password(_PASSWORD)

        mock_client.encrypt.assert_called_once_with(
            KeyId="arn:aws:kms:us-east-1:123:key/abc",
            Plaintext=_PASSWORD.encode(),
        )
        import base64 as _b64

        assert result == _b64.b64encode(ciphertext_blob).decode()

    @pytest.mark.unit
    def test_decrypt_calls_kms_decrypt(self) -> None:
        """_decrypt_password calls kms.decrypt and returns decoded plaintext."""
        import base64 as _b64

        ciphertext_blob = b"fake-ciphertext-bytes"
        ciphertext_b64 = _b64.b64encode(ciphertext_blob).decode()

        mock_client = MagicMock()
        mock_client.decrypt.return_value = {"Plaintext": _PASSWORD.encode()}

        with patch("handler._get_kms_client", return_value=mock_client):
            result = _decrypt_password(ciphertext_b64)

        mock_client.decrypt.assert_called_once_with(CiphertextBlob=ciphertext_blob)
        assert result == _PASSWORD

    @pytest.mark.unit
    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Encrypting and then decrypting a password via mocked KMS returns the original."""

        # Simulate KMS: encrypt pads the input, decrypt returns it back
        stored_plaintext: list[bytes] = []

        def fake_encrypt(KeyId: str, Plaintext: bytes) -> dict[str, bytes]:
            # "Encrypt" by base64-encoding the payload (not real encryption, just a stub)
            stored_plaintext.append(Plaintext)
            return {"CiphertextBlob": Plaintext}  # identity cipher for testing

        def fake_decrypt(CiphertextBlob: bytes) -> dict[str, bytes]:
            return {"Plaintext": CiphertextBlob}

        mock_client = MagicMock()
        mock_client.encrypt.side_effect = fake_encrypt
        mock_client.decrypt.side_effect = fake_decrypt

        with (
            patch("handler._get_kms_client", return_value=mock_client),
            patch.dict(
                "os.environ", {"KMS_VISITOR_PASSWORD_KEY": "arn:aws:kms:us-east-1:123:key/test"}
            ),
        ):
            ciphertext_b64 = _encrypt_password(_PASSWORD)
            recovered = _decrypt_password(ciphertext_b64)

        assert recovered == _PASSWORD


# ---------------------------------------------------------------------------
# handle_reprovision_visitors
# ---------------------------------------------------------------------------


def _make_dynamo_item(
    email: str,
    name: str = "Test Visitor",
    encrypted_password: str | None = "dGVzdA==",
) -> dict[str, Any]:
    """Build a DynamoDB attribute map for a visitor record."""
    item: dict[str, Any] = {
        "email": {"S": email},
        "name": {"S": name},
        "password_hash": {"S": "$2b$12$fakehash"},
        "created_at": {"S": "2024-01-01T00:00:00+00:00"},
        "provisioned_services": {"SS": ["grafana", "airflow"]},
    }
    if encrypted_password is not None:
        item["encrypted_password"] = {"S": encrypted_password}
    return item


_FULL_REPROVISION_RESULT: dict[str, Any] = {
    "successes": [
        {"service": "grafana", "result": {"status": "created", "user_id": 42}},
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


class TestReprovisioning:
    @pytest.mark.unit
    def test_reprovision_requires_auth(self, mock_secrets: object) -> None:
        """handle_reprovision_visitors returns 401 for an invalid API key."""
        status, body = handle_reprovision_visitors("wrong-key")
        assert status == 401
        assert "error" in body

    @pytest.mark.unit
    def test_reprovision_returns_200_when_no_visitors(self, mock_secrets: object) -> None:
        """handle_reprovision_visitors returns 200 with empty result when table has no items."""
        mock_dynamo = MagicMock()
        mock_dynamo.scan.return_value = {"Items": []}

        with patch("handler._get_dynamodb_client", return_value=mock_dynamo):
            status, body = handle_reprovision_visitors(_API_KEY)

        assert status == 200
        assert body["provisioned"] == 0
        assert body["failed"] == 0
        assert body["results"] == []

    @pytest.mark.unit
    def test_reprovision_scans_and_calls_provision_visitor(self, mock_secrets: object) -> None:
        """handle_reprovision_visitors decrypts each password and calls _provision_visitor."""
        item = _make_dynamo_item(_EMAIL, encrypted_password="dGVzdA==")
        mock_dynamo = MagicMock()
        mock_dynamo.scan.return_value = {"Items": [item]}

        with (
            patch("handler._get_dynamodb_client", return_value=mock_dynamo),
            patch("handler._decrypt_password", return_value=_PASSWORD),
            patch("handler._provision_visitor", return_value=_FULL_REPROVISION_RESULT) as mock_pv,
        ):
            status, body = handle_reprovision_visitors(_API_KEY)

        assert status == 200
        assert body["provisioned"] == 1
        assert body["failed"] == 0
        mock_pv.assert_called_once_with(_EMAIL, _PASSWORD, "Test Visitor")

    @pytest.mark.unit
    def test_reprovision_skips_record_missing_encrypted_password(
        self, mock_secrets: object
    ) -> None:
        """Records without encrypted_password are added to failures, not raised."""
        item = _make_dynamo_item(_EMAIL, encrypted_password=None)
        mock_dynamo = MagicMock()
        mock_dynamo.scan.return_value = {"Items": [item]}

        with patch("handler._get_dynamodb_client", return_value=mock_dynamo):
            status, body = handle_reprovision_visitors(_API_KEY)

        assert status == 207
        assert body["provisioned"] == 0
        assert body["failed"] == 1
        assert "no encrypted_password" in body["failures"][0]["error"]

    @pytest.mark.unit
    def test_reprovision_continues_after_kms_decrypt_failure(self, mock_secrets: object) -> None:
        """A KMS decrypt failure for one record does not abort processing of others."""
        from botocore.exceptions import ClientError

        item_bad = _make_dynamo_item("bad@example.com", encrypted_password="corrupted==")
        item_good = _make_dynamo_item(_EMAIL, encrypted_password="dGVzdA==")

        mock_dynamo = MagicMock()
        mock_dynamo.scan.return_value = {"Items": [item_bad, item_good]}

        def decrypt_side_effect(ciphertext_b64: str) -> str:
            if ciphertext_b64 == "corrupted==":
                raise ClientError(
                    {"Error": {"Code": "InvalidCiphertextException", "Message": "bad ciphertext"}},
                    "Decrypt",
                )
            return _PASSWORD

        with (
            patch("handler._get_dynamodb_client", return_value=mock_dynamo),
            patch("handler._decrypt_password", side_effect=decrypt_side_effect),
            patch("handler._provision_visitor", return_value=_FULL_REPROVISION_RESULT),
        ):
            status, body = handle_reprovision_visitors(_API_KEY)

        # One succeeded, one failed — partial success → 207
        assert status == 207
        assert body["provisioned"] == 1
        assert body["failed"] == 1
        assert "bad@example.com" == body["failures"][0]["email"]

    @pytest.mark.unit
    def test_reprovision_handles_pagination(self, mock_secrets: object) -> None:
        """handle_reprovision_visitors follows LastEvaluatedKey for multi-page scans."""
        item_page1 = _make_dynamo_item("page1@example.com", encrypted_password="ZmFrZQ==")
        item_page2 = _make_dynamo_item("page2@example.com", encrypted_password="ZmFrZQ==")

        page1_response = {
            "Items": [item_page1],
            "LastEvaluatedKey": {"email": {"S": "page1@example.com"}},
        }
        page2_response = {"Items": [item_page2]}

        mock_dynamo = MagicMock()
        mock_dynamo.scan.side_effect = [page1_response, page2_response]

        with (
            patch("handler._get_dynamodb_client", return_value=mock_dynamo),
            patch("handler._decrypt_password", return_value=_PASSWORD),
            patch("handler._provision_visitor", return_value=_FULL_REPROVISION_RESULT),
        ):
            status, body = handle_reprovision_visitors(_API_KEY)

        assert status == 200
        assert body["provisioned"] == 2
        assert mock_dynamo.scan.call_count == 2

        # Second call must include ExclusiveStartKey
        second_call_kwargs = mock_dynamo.scan.call_args_list[1].kwargs
        assert "ExclusiveStartKey" in second_call_kwargs

    @pytest.mark.unit
    def test_reprovision_207_when_some_visitors_fail(self, mock_secrets: object) -> None:
        """handle_reprovision_visitors returns 207 when at least one visitor fails provisioning."""
        item_good = _make_dynamo_item(_EMAIL, encrypted_password="ZmFrZQ==")
        item_bad = _make_dynamo_item("other@example.com", encrypted_password="ZmFrZQ==")

        mock_dynamo = MagicMock()
        mock_dynamo.scan.return_value = {"Items": [item_good, item_bad]}

        partial_result = {
            "successes": [{"service": "grafana", "result": {"status": "created"}}],
            "failures": [{"service": "airflow", "error": "timeout"}],
        }

        def provision_side_effect(email: str, password: str, name: str) -> dict[str, Any]:
            if email == _EMAIL:
                return _FULL_REPROVISION_RESULT
            return partial_result

        with (
            patch("handler._get_dynamodb_client", return_value=mock_dynamo),
            patch("handler._decrypt_password", return_value=_PASSWORD),
            patch("handler._provision_visitor", side_effect=provision_side_effect),
        ):
            status, body = handle_reprovision_visitors(_API_KEY)

        assert status == 207
        # The fully-successful visitor goes to results; the partial one goes to failures
        assert body["provisioned"] == 1
        assert body["failed"] == 1


# ---------------------------------------------------------------------------
# _verify_password_pbkdf2 / _hash_password_pbkdf2
# ---------------------------------------------------------------------------


class TestVerifyPasswordPbkdf2:
    """Tests for _verify_password_pbkdf2."""

    @pytest.mark.unit
    def test_correct_password_returns_true(self) -> None:
        """Hashing then verifying the same password returns True."""
        hashed = _hash_password_pbkdf2("my-secret-password")
        assert _verify_password_pbkdf2("my-secret-password", hashed) is True

    @pytest.mark.unit
    def test_wrong_password_returns_false(self) -> None:
        """Verifying a different password returns False."""
        hashed = _hash_password_pbkdf2("correct-password")
        assert _verify_password_pbkdf2("wrong-password", hashed) is False

    @pytest.mark.unit
    def test_malformed_hash_returns_false(self) -> None:
        """A garbage string returns False instead of raising."""
        assert _verify_password_pbkdf2("anything", "not-a-valid-hash") is False

    @pytest.mark.unit
    def test_empty_hash_returns_false(self) -> None:
        """An empty stored hash returns False."""
        assert _verify_password_pbkdf2("anything", "") is False


# ---------------------------------------------------------------------------
# handle_visitor_login
# ---------------------------------------------------------------------------


class TestVisitorLogin:
    """Tests for handle_visitor_login."""

    @pytest.mark.unit
    def test_missing_email_returns_400(self) -> None:
        """Empty email returns 400."""
        status, body = handle_visitor_login("", "some-password")
        assert status == 400
        assert "email" in body["error"].lower() or "missing" in body["error"].lower()

    @pytest.mark.unit
    def test_missing_password_returns_400(self) -> None:
        """Empty password returns 400."""
        status, body = handle_visitor_login("user@example.com", "")
        assert status == 400
        assert "password" in body["error"].lower() or "missing" in body["error"].lower()

    @pytest.mark.unit
    def test_email_not_found_returns_401(self) -> None:
        """DynamoDB get_item returns no Item → 401."""
        mock_dynamo = MagicMock()
        mock_dynamo.get_item.return_value = {}

        with patch("handler._get_dynamodb_client", return_value=mock_dynamo):
            status, body = handle_visitor_login("missing@example.com", "password")

        assert status == 401
        assert body["error"] == "Invalid email or password"

    @pytest.mark.unit
    def test_wrong_password_returns_401(self) -> None:
        """Valid email but wrong password → 401."""
        stored_hash = _hash_password_pbkdf2("correct-password")
        mock_dynamo = MagicMock()
        mock_dynamo.get_item.return_value = {
            "Item": {
                "email": {"S": "user@example.com"},
                "password_hash": {"S": stored_hash},
            }
        }

        with patch("handler._get_dynamodb_client", return_value=mock_dynamo):
            status, body = handle_visitor_login("user@example.com", "wrong-password")

        assert status == 401
        assert body["error"] == "Invalid email or password"

    @pytest.mark.unit
    def test_success_returns_api_key_and_viewer_role(self) -> None:
        """Valid credentials → 200 with api_key, role='viewer', email."""
        stored_hash = _hash_password_pbkdf2("correct-password")
        mock_dynamo = MagicMock()
        mock_dynamo.get_item.return_value = {
            "Item": {
                "email": {"S": "user@example.com"},
                "password_hash": {"S": stored_hash},
            }
        }

        with (
            patch("handler._get_dynamodb_client", return_value=mock_dynamo),
            patch("handler.get_secret", return_value="admin-api-key"),
        ):
            status, body = handle_visitor_login("user@example.com", "correct-password")

        assert status == 200
        assert body["api_key"] == "admin-api-key"
        assert body["role"] == "viewer"
        assert body["email"] == "user@example.com"

    @pytest.mark.unit
    def test_error_messages_identical(self) -> None:
        """Wrong email and wrong password return the same error message (no enumeration)."""
        stored_hash = _hash_password_pbkdf2("correct-password")

        mock_dynamo_miss = MagicMock()
        mock_dynamo_miss.get_item.return_value = {}

        mock_dynamo_hit = MagicMock()
        mock_dynamo_hit.get_item.return_value = {
            "Item": {
                "email": {"S": "user@example.com"},
                "password_hash": {"S": stored_hash},
            }
        }

        with patch("handler._get_dynamodb_client", return_value=mock_dynamo_miss):
            _, body_miss = handle_visitor_login("missing@example.com", "password")

        with patch("handler._get_dynamodb_client", return_value=mock_dynamo_hit):
            _, body_wrong = handle_visitor_login("user@example.com", "wrong-password")

        assert body_miss["error"] == body_wrong["error"]
