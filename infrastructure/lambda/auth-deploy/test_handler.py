import json
from unittest.mock import patch

import pytest

from handler import (
    get_response_headers,
    handle_auto_teardown,
    handle_deploy,
    handle_service_health,
    handle_session_status,
    handle_status,
    handle_validate,
    lambda_handler,
    validate_api_key,
)


@pytest.fixture()
def mock_secrets():
    """Mock Secrets Manager responses."""
    with patch("handler.get_secret") as mock:
        mock.side_effect = lambda secret_id: {
            "rideshare/api-key": "test-api-key",
            "rideshare/github-pat": "ghp_test_token",
        }[secret_id]
        yield mock


@pytest.fixture()
def mock_github_api():
    """Mock GitHub API requests."""
    with patch("handler.github_api_request") as mock:
        yield mock


class TestValidateApiKey:
    def test_success(self, mock_secrets: object) -> None:
        assert validate_api_key("test-api-key") is True

    def test_failure(self, mock_secrets: object) -> None:
        assert validate_api_key("wrong-key") is False


class TestHandleValidate:
    def test_success(self, mock_secrets: object) -> None:
        status, body = handle_validate("test-api-key")
        assert status == 200
        assert body["valid"] is True

    def test_failure(self, mock_secrets: object) -> None:
        status, body = handle_validate("wrong-key")
        assert status == 401
        assert body["valid"] is False
        assert "error" in body


class TestHandleDeploy:
    def test_success(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (204, {})

        status, body = handle_deploy("test-api-key")
        assert status == 200
        assert body["triggered"] is True
        assert body["workflow"] == "deploy.yml"

        # Verify GitHub API was called correctly
        mock_github_api.assert_called_once()
        call_args = mock_github_api.call_args
        assert call_args[0][0] == "POST"
        assert "dispatches" in call_args[0][1]

    def test_invalid_key(self, mock_secrets: object) -> None:
        status, body = handle_deploy("wrong-key")
        assert status == 401
        assert "error" in body

    def test_github_error(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (422, {"message": "Workflow not found"})

        status, body = handle_deploy("test-api-key")
        assert status == 502
        assert "error" in body
        assert body["status_code"] == 422

    def test_dbt_runner_forwarded(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (204, {})

        handle_deploy("test-api-key", "glue")

        call_args = mock_github_api.call_args
        dispatch_body = call_args[0][3]
        assert dispatch_body["inputs"]["dbt_runner"] == "glue"

    def test_dbt_runner_defaults_to_duckdb(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        mock_github_api.return_value = (204, {})

        handle_deploy("test-api-key")

        call_args = mock_github_api.call_args
        dispatch_body = call_args[0][3]
        assert dispatch_body["inputs"]["dbt_runner"] == "duckdb"


class TestHandleStatus:
    def test_success(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (
            200,
            {
                "workflow_runs": [
                    {
                        "status": "in_progress",
                        "conclusion": None,
                        "id": 123456,
                        "created_at": "2026-02-20T12:00:00Z",
                        "html_url": "https://github.com/...",
                    }
                ]
            },
        )

        status, body = handle_status("test-api-key")
        assert status == 200
        assert body["status"] == "in_progress"
        assert body["run_id"] == 123456

    def test_no_runs(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (200, {"workflow_runs": []})

        status, body = handle_status("test-api-key")
        assert status == 200
        assert body["status"] == "idle"

    def test_invalid_key(self, mock_secrets: object) -> None:
        status, body = handle_status("wrong-key")
        assert status == 401
        assert "error" in body


class TestResponseHeaders:
    def test_content_type(self) -> None:
        headers = get_response_headers()
        assert headers["Content-Type"] == "application/json"

    def test_no_cors_headers(self) -> None:
        """CORS is handled by Lambda Function URL config, not the handler."""
        headers = get_response_headers()
        assert "Access-Control-Allow-Origin" not in headers
        assert "Access-Control-Allow-Methods" not in headers


class TestLambdaHandler:
    def test_validate(self, mock_secrets: object) -> None:
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {"Origin": "http://localhost:5173"},
            "body": json.dumps({"action": "validate", "api_key": "test-api-key"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        assert response["headers"]["Content-Type"] == "application/json"

        body = json.loads(response["body"])
        assert body["valid"] is True

    def test_invalid_json(self) -> None:
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {},
            "body": "not json",
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid JSON" in body["error"]

    def test_missing_action(self) -> None:
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {},
            "body": json.dumps({"api_key": "test-key"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "action" in body["error"]

    def test_missing_api_key(self) -> None:
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {},
            "body": json.dumps({"action": "validate"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "api_key" in body["error"]

    def test_unknown_action(self) -> None:
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {},
            "body": json.dumps({"action": "unknown", "api_key": "test-key"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Unknown action" in body["error"]
        assert "valid_actions" in body

    def test_deploy_action(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (204, {})

        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {"Origin": "http://localhost:5173"},
            "body": json.dumps({"action": "deploy", "api_key": "test-api-key"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["triggered"] is True

    def test_status_action(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (200, {"workflow_runs": []})

        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {"Origin": "http://localhost:5173"},
            "body": json.dumps({"action": "status", "api_key": "test-api-key"}),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "idle"

    def test_deploy_with_dbt_runner(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (204, {})

        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {"Origin": "http://localhost:5173"},
            "body": json.dumps(
                {"action": "deploy", "api_key": "test-api-key", "dbt_runner": "glue"}
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        call_args = mock_github_api.call_args
        dispatch_body = call_args[0][3]
        assert dispatch_body["inputs"]["dbt_runner"] == "glue"

    def test_deploy_invalid_dbt_runner(self, mock_secrets: object) -> None:
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {},
            "body": json.dumps(
                {"action": "deploy", "api_key": "test-api-key", "dbt_runner": "spark"}
            ),
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid dbt_runner" in body["error"]

    def test_service_health_no_auth(self) -> None:
        """service-health should not require api_key."""
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {},
            "body": json.dumps({"action": "service-health"}),
        }

        with patch("handler.urllib.request.urlopen"):
            response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "services" in body


class TestHandleSessionStatus:
    def test_no_session(self) -> None:
        with patch("handler.get_session", return_value=None):
            status, body = handle_session_status()
        assert status == 200
        assert body == {"active": False}

    def test_deploying_session(self) -> None:
        session = {"deployed_at": 1000000}
        with patch("handler.get_session", return_value=session), patch("handler.time") as mock_time:
            mock_time.time.return_value = 1000060
            status, body = handle_session_status()
        assert status == 200
        assert body["deploying"] is True
        assert body["active"] is False

    def test_active_session(self) -> None:
        session = {"deployed_at": 1000000, "deadline": 1001000}
        with patch("handler.get_session", return_value=session), patch("handler.time") as mock_time:
            mock_time.time.return_value = 1000500
            status, body = handle_session_status()
        assert status == 200
        assert body["active"] is True
        assert body["remaining_seconds"] == 500

    def test_tearing_down_session(self) -> None:
        session = {"deployed_at": 1000000, "deadline": 1001000, "tearing_down": True}
        with patch("handler.get_session", return_value=session), patch("handler.time") as mock_time:
            mock_time.time.return_value = 1000500
            status, body = handle_session_status()
        assert status == 200
        assert body["tearing_down"] is True
        assert body["active"] is False

    def test_tearing_down_takes_priority(self) -> None:
        """tearing_down without deadline still returns tearing_down (not deploying)."""
        session = {"deployed_at": 1000000, "tearing_down": True}
        with patch("handler.get_session", return_value=session), patch("handler.time") as mock_time:
            mock_time.time.return_value = 1000060
            status, body = handle_session_status()
        assert status == 200
        assert body["tearing_down"] is True
        assert body.get("deploying") is False

    def test_session_read_error(self) -> None:
        with patch("handler.get_session", side_effect=RuntimeError("boom")):
            status, body = handle_session_status()
        assert status == 500
        assert "error" in body


class TestHandleAutoTeardown:
    def test_sets_tearing_down_flag(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.side_effect = [
            (200, {"workflow_runs": []}),  # deploy status check
            (204, {}),  # teardown dispatch
        ]
        session = {"deployed_at": 1000000, "deadline": 1001000}
        mock_ssm = patch("handler.get_ssm_client").start()
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.get_scheduler_client"),
        ):
            handle_auto_teardown()

        # Verify SSM put_parameter was called with tearing_down: True
        put_call = mock_ssm.return_value.put_parameter
        put_call.assert_called_once()
        written_value = json.loads(put_call.call_args[1]["Value"])
        assert written_value["tearing_down"] is True
        patch.stopall()

    def test_does_not_delete_session(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.side_effect = [
            (200, {"workflow_runs": []}),  # deploy status check
            (204, {}),  # teardown dispatch
        ]
        session = {"deployed_at": 1000000, "deadline": 1001000}
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.get_ssm_client"),
            patch("handler.get_scheduler_client"),
            patch("handler.delete_session") as mock_delete,
        ):
            handle_auto_teardown()
        mock_delete.assert_not_called()

    def test_reschedules_when_deploy_in_progress(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        mock_github_api.return_value = (
            200,
            {"workflow_runs": [{"status": "in_progress"}]},
        )
        session = {"deployed_at": 1000000, "deadline": 1001000}
        with (
            patch("handler.get_session", return_value=session),
            patch("handler._upsert_schedule") as mock_schedule,
            patch("handler.update_session_deadline"),
        ):
            status, body = handle_auto_teardown()
        assert body["action"] == "rescheduled"
        mock_schedule.assert_called_once()


class TestHandleServiceHealth:
    def test_all_healthy(self) -> None:
        with patch("handler.urllib.request.urlopen"):
            status, body = handle_service_health()

        assert status == 200
        for service_id in ("simulation_api", "grafana", "airflow", "trino", "prometheus"):
            assert body["services"][service_id] is True

    def test_some_unhealthy(self) -> None:
        def fake_urlopen(req: object, timeout: float = 0) -> None:
            url = getattr(req, "full_url", "")
            if "grafana" in url or "trino" in url:
                raise ConnectionError("refused")
            from unittest.mock import MagicMock

            return MagicMock()

        with patch("handler.urllib.request.urlopen", side_effect=fake_urlopen):
            status, body = handle_service_health()

        assert status == 200
        assert body["services"]["simulation_api"] is True
        assert body["services"]["grafana"] is False
        assert body["services"]["airflow"] is True
        assert body["services"]["trino"] is False
        assert body["services"]["prometheus"] is True

    def test_all_down(self) -> None:
        with patch(
            "handler.urllib.request.urlopen",
            side_effect=ConnectionError("refused"),
        ):
            status, body = handle_service_health()

        assert status == 200
        for service_id in ("simulation_api", "grafana", "airflow", "trino", "prometheus"):
            assert body["services"][service_id] is False
