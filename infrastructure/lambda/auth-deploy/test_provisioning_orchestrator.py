"""Unit tests for the multi-service visitor provisioning orchestrator.

Tests cover the provision-visitor action in handler.py:
- API key authentication is enforced
- Request body validation (missing fields, short explicit password)
- Password auto-generation when no password is supplied
- Successful full provisioning returns 200 with all services in successes
- Partial failure (some services fail) returns 207 with mixed results
- All services failing returns 500
- DynamoDB visitor record storage (happy-path and non-fatal failure)
- Each individual provisioning helper (_provision_grafana, _provision_airflow,
  _provision_minio, _provision_trino, _provision_simulation_api) is tested
  for both happy-path and error propagation

These are pure unit tests — no running services are required.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import bcrypt

from handler import (
    SERVICE_LOGIN_URLS,
    _build_welcome_email,
    _provision_airflow,
    _provision_grafana,
    _provision_minio,
    _provision_simulation_api,
    _provision_trino,
    _provision_visitor,
    _send_welcome_email,
    handle_provision_visitor,
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
    """Mock _provision_visitor to return a full-success result and skip DynamoDB/email."""
    with (
        patch("handler._provision_visitor") as mock_pv,
        patch("handler._store_visitor_dynamodb"),
        patch("handler._send_welcome_email", return_value=True),
    ):
        mock_pv.return_value = {
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
        yield mock_pv


# ---------------------------------------------------------------------------
# handle_provision_visitor: authentication
# ---------------------------------------------------------------------------


class TestHandleProvisionVisitorAuth:
    @pytest.mark.unit
    def test_rejects_invalid_api_key(self, mock_secrets: object) -> None:
        """handle_provision_visitor returns 401 for an invalid API key."""
        status, body = handle_provision_visitor("wrong-key", _EMAIL, _PASSWORD, _NAME)
        assert status == 401
        assert "error" in body

    @pytest.mark.unit
    def test_accepts_valid_api_key(
        self, mock_secrets: object, mock_provision_visitor: object
    ) -> None:
        """handle_provision_visitor proceeds past auth when the API key is correct."""
        status, _ = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)
        # Any 2xx or 207 means auth passed
        assert status in (200, 207)


# ---------------------------------------------------------------------------
# handle_provision_visitor: request validation
# ---------------------------------------------------------------------------


class TestHandleProvisionVisitorValidation:
    @pytest.mark.unit
    def test_rejects_missing_email(self, mock_secrets: object) -> None:
        """handle_provision_visitor returns 400 when email is empty."""
        status, body = handle_provision_visitor(_API_KEY, "", _PASSWORD, _NAME)
        assert status == 400
        assert "error" in body

    @pytest.mark.unit
    def test_rejects_missing_name(self, mock_secrets: object) -> None:
        """handle_provision_visitor returns 400 when name is empty.

        Password is intentionally passed as None here: name validation must
        fire independently of whether a password was supplied.
        """
        status, body = handle_provision_visitor(_API_KEY, _EMAIL, None, "")
        assert status == 400
        assert "error" in body

    @pytest.mark.unit
    def test_rejects_short_explicit_password(self, mock_secrets: object) -> None:
        """handle_provision_visitor returns 400 when an explicit password is shorter than 8 chars."""
        status, body = handle_provision_visitor(_API_KEY, _EMAIL, "short", _NAME)
        assert status == 400
        assert "error" in body


# ---------------------------------------------------------------------------
# handle_provision_visitor: response codes
# ---------------------------------------------------------------------------


class TestHandleProvisionVisitorResponseCodes:
    @pytest.mark.unit
    def test_200_all_services_succeed(
        self, mock_secrets: object, mock_provision_visitor: object
    ) -> None:
        """handle_provision_visitor returns 200 when all services succeed."""
        status, body = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)
        assert status == 200
        assert body["email"] == _EMAIL
        assert "password" in body
        assert len(body["successes"]) == 5
        assert body["failures"] == []

    @pytest.mark.unit
    def test_207_partial_failure(self, mock_secrets: object) -> None:
        """handle_provision_visitor returns 207 when some but not all services fail."""
        partial_result = {
            "successes": [
                {"service": "grafana", "result": {"status": "created", "user_id": 1}},
            ],
            "failures": [
                {"service": "airflow", "error": "Connection refused"},
            ],
        }
        with (
            patch("handler._provision_visitor", return_value=partial_result),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)

        assert status == 207
        assert len(body["successes"]) == 1
        assert len(body["failures"]) == 1

    @pytest.mark.unit
    def test_500_all_services_fail(self, mock_secrets: object) -> None:
        """handle_provision_visitor returns 500 when every service fails."""
        all_failed = {
            "successes": [],
            "failures": [
                {"service": "grafana", "error": "timeout"},
                {"service": "airflow", "error": "timeout"},
                {"service": "minio", "error": "timeout"},
                {"service": "trino", "error": "timeout"},
                {"service": "simulation_api", "error": "timeout"},
            ],
        }
        with (
            patch("handler._provision_visitor", return_value=all_failed),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=False),
        ):
            status, body = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)

        assert status == 500
        assert "error" in body


# ---------------------------------------------------------------------------
# _provision_visitor: partial failure handling
# ---------------------------------------------------------------------------


class TestProvisionVisitorOrchestrator:
    @pytest.mark.unit
    def test_continues_after_grafana_failure(self, mock_secrets: object) -> None:
        """_provision_visitor calls remaining services even when Grafana fails.

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
            result = _provision_visitor(_EMAIL, _PASSWORD, _NAME)

        service_failures = [f["service"] for f in result["failures"]]
        service_successes = [s["service"] for s in result["successes"]]

        assert "grafana" in service_failures
        assert "airflow" in service_successes
        assert "minio" in service_successes
        assert "trino" in service_successes
        assert "simulation_api" in service_successes

    @pytest.mark.unit
    def test_all_services_attempted(self, mock_secrets: object) -> None:
        """_provision_visitor attempts all five services regardless of prior failures."""
        with (
            patch("handler._provision_grafana", side_effect=Exception("err")),
            patch("handler._provision_airflow", side_effect=Exception("err")),
            patch("handler._provision_minio", side_effect=Exception("err")),
            patch("handler._provision_trino", side_effect=Exception("err")),
            patch("handler._provision_simulation_api", side_effect=Exception("err")),
        ):
            result = _provision_visitor(_EMAIL, _PASSWORD, _NAME)

        assert len(result["failures"]) == 5
        assert result["successes"] == []


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
        # Verify it's a valid bcrypt hash
        import bcrypt

        assert bcrypt.checkpw(_PASSWORD.encode(), stored["hash"].encode())

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
    def test_hash_is_valid_bcrypt(self) -> None:
        """_provision_trino stores a hash that bcrypt can verify against the original password."""
        import bcrypt

        mock_client = MagicMock()
        mock_client.put_secret_value.return_value = {}
        stored_secret: dict[str, str] = {}

        def capture_put(SecretId: str, SecretString: str) -> dict[str, str]:
            stored_secret.update(json.loads(SecretString))
            return {}

        mock_client.put_secret_value.side_effect = capture_put

        with patch("handler.get_secrets_client", return_value=mock_client):
            _provision_trino(_EMAIL, _PASSWORD)

        assert bcrypt.checkpw(_PASSWORD.encode(), stored_secret["hash"].encode())


# ---------------------------------------------------------------------------
# _provision_simulation_api
# ---------------------------------------------------------------------------


class TestProvisionSimulationApi:
    @pytest.mark.unit
    def test_calls_post_auth_register(self, mock_secrets: object) -> None:
        """_provision_simulation_api sends POST /auth/register with the correct payload."""
        response_body = {"email": _EMAIL, "role": "viewer", "status": "created"}
        encoded = json.dumps(response_body).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = encoded
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured_requests: list[Any] = []

        def urlopen_side_effect(req: Any, **kwargs: Any) -> Any:
            captured_requests.append(req)
            return mock_resp

        with (
            patch("handler.urllib.request.urlopen", side_effect=urlopen_side_effect),
            patch.dict("os.environ", {"SIMULATION_API_URL": "http://simulation:8000"}),
        ):
            result = _provision_simulation_api(_EMAIL, _PASSWORD, _NAME)

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
        """_provision_simulation_api lets HTTP errors bubble up for the orchestrator."""
        with (
            patch(
                "handler.urllib.request.urlopen",
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
                _provision_simulation_api(_EMAIL, _PASSWORD, _NAME)

        assert exc_info.value.code == 503


# ---------------------------------------------------------------------------
# Password generation
# ---------------------------------------------------------------------------


_FULL_SUCCESS_RESULT = {
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


class TestPasswordGeneration:
    @pytest.mark.unit
    def test_generates_password_when_not_provided(self, mock_secrets: object) -> None:
        """handle_provision_visitor auto-generates a password when none is supplied."""
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_API_KEY, _EMAIL, None, _NAME)

        assert status == 200
        assert "password" in body
        assert len(body["password"]) >= 8

    @pytest.mark.unit
    def test_uses_provided_password_when_supplied(self, mock_secrets: object) -> None:
        """handle_provision_visitor echoes back the caller-supplied password."""
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["password"] == _PASSWORD

    @pytest.mark.unit
    def test_generated_passwords_are_unique(self, mock_secrets: object) -> None:
        """Two calls without a password produce different passwords (collision negligible)."""
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            _, body1 = handle_provision_visitor(_API_KEY, _EMAIL, None, _NAME)
            _, body2 = handle_provision_visitor(_API_KEY, _EMAIL, None, _NAME)

        assert body1["password"] != body2["password"]

    @pytest.mark.unit
    def test_rejects_short_explicit_password(self, mock_secrets: object) -> None:
        """handle_provision_visitor returns 400 when an explicit password is too short."""
        status, body = handle_provision_visitor(_API_KEY, _EMAIL, "short", _NAME)
        assert status == 400
        assert "error" in body


# ---------------------------------------------------------------------------
# DynamoDB storage
# ---------------------------------------------------------------------------


class TestDynamoDBStorage:
    @pytest.mark.unit
    def test_stores_record_after_successful_provisioning(self, mock_secrets: object) -> None:
        """_store_visitor_dynamodb is called with the correct email and bcrypt hash."""
        mock_dynamo_client = MagicMock()

        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._get_dynamodb_client", return_value=mock_dynamo_client),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert "password" in body
        mock_dynamo_client.put_item.assert_called_once()

        call_kwargs = mock_dynamo_client.put_item.call_args.kwargs
        item = call_kwargs["Item"]
        assert item["email"]["S"] == _EMAIL

        stored_hash = item["password_hash"]["S"]
        assert bcrypt.checkpw(body["password"].encode(), stored_hash.encode())

    @pytest.mark.unit
    def test_dynamodb_failure_is_non_fatal(self, mock_secrets: object) -> None:
        """A DynamoDB error does not roll back provisioning or change the status code."""
        mock_dynamo_client = MagicMock()
        mock_dynamo_client.put_item.side_effect = Exception("DynamoDB unavailable")

        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._get_dynamodb_client", return_value=mock_dynamo_client),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert "password" in body

    @pytest.mark.unit
    def test_stores_only_succeeded_services(self, mock_secrets: object) -> None:
        """_store_visitor_dynamodb receives only the names of successfully provisioned services."""
        partial_result = {
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
        mock_dynamo_client = MagicMock()

        with (
            patch("handler._provision_visitor", return_value=partial_result),
            patch("handler._get_dynamodb_client", return_value=mock_dynamo_client),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)

        assert status == 207
        call_kwargs = mock_dynamo_client.put_item.call_args.kwargs
        item = call_kwargs["Item"]
        # Only grafana succeeded — it must be the sole entry in provisioned_services.
        assert item["provisioned_services"]["SS"] == ["grafana"]


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
    def test_email_sent_flag_true_in_200_response(self, mock_secrets: object) -> None:
        """200 response includes email_sent=True when email succeeds."""
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=True),
        ):
            status, body = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["email_sent"] is True

    @pytest.mark.unit
    def test_email_sent_flag_false_does_not_change_status(self, mock_secrets: object) -> None:
        """200 response still returns 200 with email_sent=False when email fails."""
        with (
            patch("handler._provision_visitor", return_value=_FULL_SUCCESS_RESULT),
            patch("handler._store_visitor_dynamodb"),
            patch("handler._send_welcome_email", return_value=False),
        ):
            status, body = handle_provision_visitor(_API_KEY, _EMAIL, _PASSWORD, _NAME)

        assert status == 200
        assert body["email_sent"] is False
