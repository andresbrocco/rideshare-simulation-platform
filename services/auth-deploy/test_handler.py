import json
from unittest.mock import patch

import pytest

from handler import (
    DEPLOY_PROGRESS_SERVICES,
    SESSION_STEP_MINUTES,
    SIMULATION_START_DEFAULTS,
    TEARDOWN_TIMEOUT_SECONDS,
    TEARDOWN_UI_LABELS,
    _log_response,
    _mask_event,
    get_response_headers,
    handle_auto_teardown,
    handle_complete_teardown,
    handle_deploy,
    handle_ensure_session,
    handle_get_deploy_progress,
    handle_report_deploy_progress,
    handle_service_health,
    handle_session_status,
    handle_set_teardown_run_id,
    handle_start_simulation,
    handle_status,
    handle_teardown_status,
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

        with patch("handler.get_session", return_value=None):
            status, body = handle_deploy("test-api-key")
        assert status == 200
        assert body["triggered"] is True
        assert body["workflow"] == "deploy-platform.yml"

        # Verify GitHub API was called correctly
        mock_github_api.assert_called_once()
        call_args = mock_github_api.call_args
        assert call_args[0][0] == "POST"
        assert "dispatches" in call_args[0][1]

    def test_invalid_key(self, mock_secrets: object) -> None:
        status, body = handle_deploy("wrong-key")
        assert status == 401
        assert "error" in body

    def test_rejects_when_session_exists(self, mock_secrets: object) -> None:
        """Reject deploy if a session already exists (prevents double-deploy race)."""
        session = {"deployed_at": 1000000}
        with patch("handler.get_session", return_value=session):
            status, body = handle_deploy("test-api-key")
        assert status == 409
        assert "already in progress" in body["error"]

    def test_github_error(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (422, {"message": "Workflow not found"})

        with patch("handler.get_session", return_value=None):
            status, body = handle_deploy("test-api-key")
        assert status == 502
        assert "error" in body
        assert body["status_code"] == 422

    def test_dbt_runner_forwarded(self, mock_secrets: object, mock_github_api: object) -> None:
        mock_github_api.return_value = (204, {})

        with patch("handler.get_session", return_value=None):
            handle_deploy("test-api-key", "glue")

        call_args = mock_github_api.call_args
        dispatch_body = call_args[0][3]
        assert dispatch_body["inputs"]["dbt_runner"] == "glue"

    def test_dbt_runner_defaults_to_duckdb(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        mock_github_api.return_value = (204, {})

        with patch("handler.get_session", return_value=None):
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

        with patch("handler.get_session", return_value=None):
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

        with patch("handler.get_session", return_value=None):
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

    def test_teardown_status_no_auth(self) -> None:
        """teardown-status should not require api_key."""
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {},
            "body": json.dumps({"action": "teardown-status"}),
        }

        with patch("handler.get_session", return_value=None):
            response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["tearing_down"] is False

    def test_ensure_session_action(self, mock_secrets: object) -> None:
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "headers": {},
            "body": json.dumps({"action": "ensure-session", "api_key": "test-api-key"}),
        }

        with (
            patch("handler.get_session", return_value=None),
            patch("handler.create_session"),
        ):
            response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert body["created"] is True


class TestHandleEnsureSession:
    def test_invalid_key(self, mock_secrets: object) -> None:
        status, body = handle_ensure_session("wrong-key")
        assert status == 401
        assert "Invalid password" in body["error"]

    def test_no_session_creates_new(self, mock_secrets: object) -> None:
        with (
            patch("handler.get_session", return_value=None),
            patch("handler.create_session") as mock_create,
        ):
            status, body = handle_ensure_session("test-api-key")

        assert status == 200
        assert body["success"] is True
        assert body["created"] is True
        assert body["remaining_seconds"] == SESSION_STEP_MINUTES * 60
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert (
            call_kwargs[1]["deployed_at"] == call_kwargs[1]["deadline"] - SESSION_STEP_MINUTES * 60
        )

    def test_deploying_session_activates(self, mock_secrets: object) -> None:
        deploying_session = {"deployed_at": 1000000}
        with (
            patch("handler.get_session", return_value=deploying_session),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_ensure_session("test-api-key")

        assert status == 200
        assert body["success"] is True
        assert body["created"] is False
        assert body["remaining_seconds"] == SESSION_STEP_MINUTES * 60
        mock_update.assert_called_once()
        # Deadline should be now + SESSION_STEP_MINUTES
        actual_deadline = mock_update.call_args[0][0]
        assert body["deadline"] == actual_deadline

    def test_already_activated_resets_deadline(self, mock_secrets: object) -> None:
        import time as time_mod

        now = int(time_mod.time())
        active_session = {"deployed_at": now - 300, "deadline": now + 600}
        with (
            patch("handler.get_session", return_value=active_session),
            patch("handler.update_session_deadline") as mock_update,
        ):
            status, body = handle_ensure_session("test-api-key")

        assert status == 200
        assert body["success"] is True
        assert body["created"] is False
        assert body["remaining_seconds"] == SESSION_STEP_MINUTES * 60
        mock_update.assert_called_once()
        actual_deadline = mock_update.call_args[0][0]
        assert body["deadline"] == actual_deadline

    def test_create_session_failure(self, mock_secrets: object) -> None:
        with (
            patch("handler.get_session", return_value=None),
            patch("handler.create_session", side_effect=Exception("SSM error")),
        ):
            status, body = handle_ensure_session("test-api-key")

        assert status == 500
        assert "Failed to create session" in body["error"]

    def test_activate_deploying_failure(self, mock_secrets: object) -> None:
        deploying_session = {"deployed_at": 1000000}
        with (
            patch("handler.get_session", return_value=deploying_session),
            patch("handler.update_session_deadline", side_effect=Exception("Schedule error")),
        ):
            status, body = handle_ensure_session("test-api-key")

        assert status == 500
        assert "Failed to activate deploying session" in body["error"]


class TestHandleSessionStatus:
    def test_no_session(self) -> None:
        with patch("handler.get_session", return_value=None):
            status, body = handle_session_status()
        assert status == 200
        assert body == {"active": False}

    def test_deploying_session(self) -> None:
        session = {"deployed_at": 1000000}
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.get_secret", side_effect=Exception("no creds")),
        ):
            mock_time.time.return_value = 1000060
            status, body = handle_session_status()
        assert status == 200
        assert body["deploying"] is True
        assert body["active"] is False

    def test_deploying_auto_clears_after_timeout(self) -> None:
        """Stale deploying session is auto-cleared after DEPLOYING_TIMEOUT_SECONDS."""
        session = {"deployed_at": 1000000}
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
        ):
            mock_time.time.return_value = 1000000 + 30 * 60 + 1  # just past 30 min timeout
            status, body = handle_session_status()
        assert status == 200
        assert body == {"active": False}
        mock_delete.assert_called_once()

    def test_deploying_no_clear_before_timeout(self) -> None:
        """Deploying session is NOT cleared before timeout expires."""
        session = {"deployed_at": 1000000}
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
            patch("handler.get_secret", side_effect=Exception("no creds")),
        ):
            mock_time.time.return_value = 1000000 + 20 * 60  # 20 min, before timeout
            status, body = handle_session_status()
        assert status == 200
        assert body["deploying"] is True
        mock_delete.assert_not_called()

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
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.get_secret", side_effect=Exception("no creds")),
        ):
            mock_time.time.return_value = 1000500
            status, body = handle_session_status()
        assert status == 200
        assert body["tearing_down"] is True
        assert body["active"] is False

    def test_tearing_down_takes_priority(self) -> None:
        """tearing_down without deadline still returns tearing_down (not deploying)."""
        session = {"deployed_at": 1000000, "tearing_down": True}
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.get_secret", side_effect=Exception("no creds")),
        ):
            mock_time.time.return_value = 1000060
            status, body = handle_session_status()
        assert status == 200
        assert body["tearing_down"] is True
        assert body.get("deploying") is False

    def test_tearing_down_auto_clears_after_timeout(self) -> None:
        """Stale tearing_down flag is auto-cleared after TEARDOWN_TIMEOUT_SECONDS."""
        session = {
            "deployed_at": 1000000,
            "deadline": 1001000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
        }
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
        ):
            mock_time.time.return_value = (
                1001000 + TEARDOWN_TIMEOUT_SECONDS + 1
            )  # just past timeout
            status, body = handle_session_status()
        assert status == 200
        assert body == {"active": False}
        mock_delete.assert_called_once()

    def test_tearing_down_no_clear_before_timeout(self) -> None:
        """tearing_down flag is NOT cleared before timeout expires."""
        session = {
            "deployed_at": 1000000,
            "deadline": 1001000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
        }
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
            patch("handler.get_secret", side_effect=Exception("no creds")),
        ):
            mock_time.time.return_value = 1001000 + 10 * 60  # 10 min, before timeout
            status, body = handle_session_status()
        assert status == 200
        assert body["tearing_down"] is True
        mock_delete.assert_not_called()

    def test_tearing_down_includes_tearing_down_at(self) -> None:
        """tearing_down response includes tearing_down_at timestamp."""
        session = {
            "deployed_at": 1000000,
            "deadline": 1001000,
            "tearing_down": True,
            "tearing_down_at": 1001050,
        }
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.get_secret", side_effect=Exception("no creds")),
        ):
            mock_time.time.return_value = 1001100
            status, body = handle_session_status()
        assert status == 200
        assert body["tearing_down_at"] == 1001050

    def test_tearing_down_auto_clears_without_timestamp(self) -> None:
        """Stale tearing_down without tearing_down_at falls back to deadline."""
        session = {
            "deployed_at": 1000000,
            "deadline": 1001000,
            "tearing_down": True,
        }
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
        ):
            mock_time.time.return_value = 1001000 + TEARDOWN_TIMEOUT_SECONDS + 1
            status, body = handle_session_status()
        assert status == 200
        assert body == {"active": False}
        mock_delete.assert_called_once()

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

        # Verify SSM put_parameter was called with tearing_down: True and timestamp
        put_call = mock_ssm.return_value.put_parameter
        put_call.assert_called_once()
        written_value = json.loads(put_call.call_args[1]["Value"])
        assert written_value["tearing_down"] is True
        assert "tearing_down_at" in written_value
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


class TestHandleTeardownStatus:
    def test_not_tearing_down(self) -> None:
        session = {"deployed_at": 1000000, "deadline": 1001000}
        with patch("handler.get_session", return_value=session):
            status, body = handle_teardown_status()
        assert status == 200
        assert body == {"tearing_down": False}

    def test_no_session(self) -> None:
        with patch("handler.get_session", return_value=None):
            status, body = handle_teardown_status()
        assert status == 200
        assert body == {"tearing_down": False}

    def test_with_run_id_in_ssm(self, mock_secrets: object, mock_github_api: object) -> None:
        """Run ID already cached in session — queries jobs API directly."""
        session = {
            "deployed_at": 1000000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
            "teardown_run_id": 99999,
        }
        # Mock jobs API response: steps 0-4 completed, step 5 in_progress
        job_steps = []
        for i in range(11):
            if i < 5:
                job_steps.append({"name": f"Step {i}", "status": "completed"})
            elif i == 5:
                job_steps.append({"name": f"Step {i}", "status": "in_progress"})
            else:
                job_steps.append({"name": f"Step {i}", "status": "queued"})

        mock_github_api.return_value = (
            200,
            {
                "jobs": [
                    {
                        "status": "in_progress",
                        "conclusion": None,
                        "steps": job_steps,
                    }
                ],
            },
        )

        with patch("handler.get_session", return_value=session):
            status, body = handle_teardown_status()

        assert status == 200
        assert body["tearing_down"] is True
        assert body["run_id"] == 99999
        assert body["current_step"] == 1  # DNS step (workflow step 5)
        assert body["steps"][0]["status"] == "completed"  # checkpoint
        assert body["steps"][1]["status"] == "in_progress"  # DNS
        assert body["steps"][2]["status"] == "pending"  # terraform

    def test_resolves_run_id_from_workflow_runs(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        """No run_id yet — queries runs API then jobs API."""
        session = {
            "deployed_at": 1000000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
        }

        # First call: workflow runs query
        runs_response = (
            200,
            {
                "workflow_runs": [
                    {
                        "id": 77777,
                        "created_at": "2001-09-09T01:46:40Z",  # ts=1000000
                        "status": "in_progress",
                    }
                ],
            },
        )
        # Second call: jobs API
        jobs_response = (
            200,
            {
                "jobs": [
                    {
                        "status": "in_progress",
                        "conclusion": None,
                        "steps": [{"name": f"Step {i}", "status": "queued"} for i in range(11)],
                    }
                ],
            },
        )
        mock_github_api.side_effect = [runs_response, jobs_response]

        mock_ssm = patch("handler.get_ssm_client").start()
        with patch("handler.get_session", return_value=session):
            status, body = handle_teardown_status()

        assert status == 200
        assert body["run_id"] == 77777
        # Verify run_id was cached in SSM
        put_call = mock_ssm.return_value.put_parameter
        put_call.assert_called_once()
        written_value = json.loads(put_call.call_args[1]["Value"])
        assert written_value["teardown_run_id"] == 77777
        patch.stopall()

    def test_run_not_found(self, mock_secrets: object, mock_github_api: object) -> None:
        """No matching run found — returns all steps pending."""
        session = {
            "deployed_at": 1000000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
        }
        # Runs API returns empty
        mock_github_api.return_value = (200, {"workflow_runs": []})

        with patch("handler.get_session", return_value=session):
            status, body = handle_teardown_status()

        assert status == 200
        assert body["tearing_down"] is True
        assert body["run_id"] is None
        assert body["current_step"] == -1
        assert all(s["status"] == "pending" for s in body["steps"])

    def test_completed_workflow(self, mock_secrets: object, mock_github_api: object) -> None:
        """All steps completed — conclusion is success."""
        session = {
            "deployed_at": 1000000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
            "teardown_run_id": 88888,
        }
        mock_github_api.return_value = (
            200,
            {
                "jobs": [
                    {
                        "status": "completed",
                        "conclusion": "success",
                        "steps": [{"name": f"Step {i}", "status": "completed"} for i in range(11)],
                    }
                ],
            },
        )

        with patch("handler.get_session", return_value=session):
            status, body = handle_teardown_status()

        assert status == 200
        assert body["workflow_conclusion"] == "success"
        assert all(s["status"] == "completed" for s in body["steps"])
        assert body["current_step"] == 4  # last step

    def test_github_api_error(self, mock_secrets: object, mock_github_api: object) -> None:
        """GitHub API fails gracefully — all steps pending."""
        session = {
            "deployed_at": 1000000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
            "teardown_run_id": 88888,
        }
        mock_github_api.side_effect = Exception("API down")

        with patch("handler.get_session", return_value=session):
            status, body = handle_teardown_status()

        assert status == 200
        assert body["tearing_down"] is True
        assert body["current_step"] == -1
        assert all(s["status"] == "pending" for s in body["steps"])

    def test_step_mapping_logic(self, mock_secrets: object, mock_github_api: object) -> None:
        """Verify TEARDOWN_STEP_RANGES mapping works correctly."""
        session = {
            "deployed_at": 1000000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
            "teardown_run_id": 11111,
        }
        # Steps 0-6 completed, 7 in_progress (UI step 3 = verifying)
        job_steps = []
        for i in range(11):
            if i <= 6:
                job_steps.append({"name": f"Step {i}", "status": "completed"})
            elif i == 7:
                job_steps.append({"name": f"Step {i}", "status": "in_progress"})
            else:
                job_steps.append({"name": f"Step {i}", "status": "queued"})

        mock_github_api.return_value = (
            200,
            {
                "jobs": [
                    {
                        "status": "in_progress",
                        "conclusion": None,
                        "steps": job_steps,
                    }
                ],
            },
        )

        with patch("handler.get_session", return_value=session):
            status, body = handle_teardown_status()

        assert status == 200
        assert body["total_steps"] == 5
        assert len(body["steps"]) == 5
        assert body["steps"][0]["status"] == "completed"  # Saving checkpoint (0-4)
        assert body["steps"][1]["status"] == "completed"  # DNS (5)
        assert body["steps"][2]["status"] == "completed"  # Terraform (6)
        assert body["steps"][3]["status"] == "in_progress"  # Verifying (7-9)
        assert body["steps"][4]["status"] == "pending"  # Finalizing (10)
        assert body["current_step"] == 3
        for step, label in zip(body["steps"], TEARDOWN_UI_LABELS):
            assert step["name"] == label


class TestReportDeployProgress:
    def test_success(self, mock_secrets: object) -> None:
        session = {"deployed_at": 1000000}
        mock_ssm = patch("handler.get_ssm_client").start()
        with patch("handler.get_session", return_value=session):
            status, body = handle_report_deploy_progress("test-api-key", "kafka", True)
        assert status == 200
        assert body["services"]["kafka"] is True
        assert body["all_ready"] is False
        mock_ssm.return_value.put_parameter.assert_called_once()
        patch.stopall()

    def test_no_session(self, mock_secrets: object) -> None:
        with patch("handler.get_session", return_value=None):
            status, body = handle_report_deploy_progress("test-api-key", "kafka", True)
        assert status == 404

    def test_invalid_service(self, mock_secrets: object) -> None:
        session = {"deployed_at": 1000000}
        with patch("handler.get_session", return_value=session):
            status, body = handle_report_deploy_progress("test-api-key", "nonexistent", True)
        assert status == 400
        assert "Unknown service" in body["error"]

    def test_all_ready_detection(self, mock_secrets: object) -> None:
        progress = {svc: True for svc in DEPLOY_PROGRESS_SERVICES}
        # Remove one to set it via the handler
        last_svc = DEPLOY_PROGRESS_SERVICES[-1]
        del progress[last_svc]
        session = {"deployed_at": 1000000, "deploy_progress": progress}
        patch("handler.get_ssm_client").start()
        with patch("handler.get_session", return_value=session):
            status, body = handle_report_deploy_progress("test-api-key", last_svc, True)
        assert status == 200
        assert body["all_ready"] is True
        patch.stopall()

    def test_invalid_key(self, mock_secrets: object) -> None:
        status, body = handle_report_deploy_progress("wrong-key", "kafka", True)
        assert status == 401


class TestGetDeployProgress:
    def test_no_session(self) -> None:
        with patch("handler.get_session", return_value=None):
            status, body = handle_get_deploy_progress()
        assert status == 200
        assert body == {"services": {}, "all_ready": False}

    def test_partial_progress(self) -> None:
        session = {
            "deployed_at": 1000000,
            "deploy_progress": {"kafka": True, "redis": True},
        }
        with patch("handler.get_session", return_value=session):
            status, body = handle_get_deploy_progress()
        assert status == 200
        assert body["services"]["kafka"] is True
        assert body["services"]["redis"] is True
        assert body["all_ready"] is False

    def test_all_ready(self) -> None:
        progress = {svc: True for svc in DEPLOY_PROGRESS_SERVICES}
        session = {"deployed_at": 1000000, "deploy_progress": progress}
        with patch("handler.get_session", return_value=session):
            status, body = handle_get_deploy_progress()
        assert status == 200
        assert body["all_ready"] is True

    def test_no_progress_field(self) -> None:
        session = {"deployed_at": 1000000}
        with patch("handler.get_session", return_value=session):
            status, body = handle_get_deploy_progress()
        assert status == 200
        assert body == {"services": {}, "all_ready": False}


class TestSetTeardownRunId:
    def test_success(self, mock_secrets: object) -> None:
        session = {"deployed_at": 1000000, "tearing_down": True}
        mock_ssm = patch("handler.get_ssm_client").start()
        with patch("handler.get_session", return_value=session):
            status, body = handle_set_teardown_run_id("test-api-key", 12345)
        assert status == 200
        assert body["run_id"] == 12345
        written = json.loads(mock_ssm.return_value.put_parameter.call_args[1]["Value"])
        assert written["teardown_run_id"] == 12345
        patch.stopall()

    def test_no_session(self, mock_secrets: object) -> None:
        with patch("handler.get_session", return_value=None):
            status, body = handle_set_teardown_run_id("test-api-key", 12345)
        assert status == 404

    def test_idempotent(self, mock_secrets: object) -> None:
        session = {"deployed_at": 1000000, "teardown_run_id": 11111}
        patch("handler.get_ssm_client").start()
        with patch("handler.get_session", return_value=session):
            status, body = handle_set_teardown_run_id("test-api-key", 22222)
        assert status == 200
        assert body["run_id"] == 22222
        patch.stopall()

    def test_invalid_key(self, mock_secrets: object) -> None:
        status, body = handle_set_teardown_run_id("wrong-key", 12345)
        assert status == 401


class TestCompleteTeardown:
    def test_success(self, mock_secrets: object) -> None:
        session = {"deployed_at": 1000000, "tearing_down": True}
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.delete_session") as mock_delete,
        ):
            status, body = handle_complete_teardown("test-api-key")
        assert status == 200
        assert body["success"] is True
        mock_delete.assert_called_once()

    def test_not_tearing_down(self, mock_secrets: object) -> None:
        session = {"deployed_at": 1000000, "deadline": 1001000}
        with patch("handler.get_session", return_value=session):
            status, body = handle_complete_teardown("test-api-key")
        assert status == 400
        assert "not in tearing_down" in body["error"]

    def test_no_session(self, mock_secrets: object) -> None:
        with patch("handler.get_session", return_value=None):
            status, body = handle_complete_teardown("test-api-key")
        assert status == 404

    def test_invalid_key(self, mock_secrets: object) -> None:
        status, body = handle_complete_teardown("wrong-key")
        assert status == 401


class TestSessionStatusGitHubValidation:
    """Tests for GitHub API state validation in session-status (Ticket 2)."""

    def test_deploying_github_keeps_when_workflow_succeeded(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        """Deploying session kept when deploy workflow completed successfully.

        The frontend will call activate-session once deploy-progress reports all_ready.
        """
        session = {"deployed_at": 1000000}
        mock_github_api.return_value = (
            200,
            {
                "workflow_runs": [
                    {
                        "status": "completed",
                        "conclusion": "success",
                        "created_at": "2001-09-09T01:46:40Z",
                    }
                ]
            },
        )
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
        ):
            mock_time.time.return_value = 1000060
            status, body = handle_session_status()
        assert status == 200
        assert body["deploying"] is True
        mock_delete.assert_not_called()

    def test_deploying_github_cleanup_when_workflow_failed(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        """Deploying session cleaned up when deploy workflow failed."""
        session = {"deployed_at": 1000000}
        mock_github_api.return_value = (
            200,
            {
                "workflow_runs": [
                    {
                        "status": "completed",
                        "conclusion": "failure",
                        "created_at": "2001-09-09T01:46:40Z",
                    }
                ]
            },
        )
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
        ):
            mock_time.time.return_value = 1000060
            status, body = handle_session_status()
        assert status == 200
        assert body == {"active": False}
        mock_delete.assert_called_once()

    def test_deploying_github_cleanup_when_workflow_cancelled(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        """Deploying session cleaned up when deploy workflow was cancelled."""
        session = {"deployed_at": 1000000}
        mock_github_api.return_value = (
            200,
            {
                "workflow_runs": [
                    {
                        "status": "completed",
                        "conclusion": "cancelled",
                        "created_at": "2001-09-09T01:46:40Z",
                    }
                ]
            },
        )
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
        ):
            mock_time.time.return_value = 1000060
            status, body = handle_session_status()
        assert status == 200
        assert body == {"active": False}
        mock_delete.assert_called_once()

    def test_deploying_github_keeps_when_workflow_running(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        """Deploying session kept when deploy workflow is in_progress."""
        session = {"deployed_at": 1000000}
        mock_github_api.return_value = (
            200,
            {"workflow_runs": [{"status": "in_progress", "created_at": "2001-09-09T01:46:40Z"}]},
        )
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
        ):
            mock_time.time.return_value = 1000060
            status, body = handle_session_status()
        assert status == 200
        assert body["deploying"] is True
        mock_delete.assert_not_called()

    def test_deploying_github_api_failure_failsafe(self, mock_secrets: object) -> None:
        """GitHub API failure during deploying check -> session kept (fail-safe)."""
        session = {"deployed_at": 1000000}
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
            patch("handler.get_secret", side_effect=Exception("API unreachable")),
        ):
            mock_time.time.return_value = 1000060
            status, body = handle_session_status()
        assert status == 200
        assert body["deploying"] is True
        mock_delete.assert_not_called()

    def test_tearing_down_github_cleanup_when_workflow_done(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        """Tearing down session cleaned up when teardown workflow is completed."""
        session = {
            "deployed_at": 1000000,
            "deadline": 1001000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
        }
        mock_github_api.return_value = (
            200,
            {"workflow_runs": [{"status": "completed", "conclusion": "success"}]},
        )
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
        ):
            mock_time.time.return_value = 1001100
            status, body = handle_session_status()
        assert status == 200
        assert body == {"active": False}
        mock_delete.assert_called_once()

    def test_tearing_down_github_keeps_when_workflow_running(
        self, mock_secrets: object, mock_github_api: object
    ) -> None:
        """Tearing down session kept when teardown workflow is in_progress."""
        session = {
            "deployed_at": 1000000,
            "deadline": 1001000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
        }
        mock_github_api.return_value = (
            200,
            {"workflow_runs": [{"status": "in_progress"}]},
        )
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
        ):
            mock_time.time.return_value = 1001100
            status, body = handle_session_status()
        assert status == 200
        assert body["tearing_down"] is True
        mock_delete.assert_not_called()

    def test_tearing_down_github_api_failure_failsafe(self, mock_secrets: object) -> None:
        """GitHub API failure during teardown check -> session kept (fail-safe)."""
        session = {
            "deployed_at": 1000000,
            "deadline": 1001000,
            "tearing_down": True,
            "tearing_down_at": 1001000,
        }
        with (
            patch("handler.get_session", return_value=session),
            patch("handler.time") as mock_time,
            patch("handler.delete_session") as mock_delete,
            patch("handler.get_secret", side_effect=Exception("API unreachable")),
        ):
            mock_time.time.return_value = 1001100
            status, body = handle_session_status()
        assert status == 200
        assert body["tearing_down"] is True
        mock_delete.assert_not_called()


class TestHandleStartSimulation:
    def test_invalid_key(self, mock_secrets: object) -> None:
        status, body = handle_start_simulation("wrong-key")
        assert status == 401
        assert "error" in body

    def test_resume_from_paused(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "paused", "drivers_total": 200, "riders_total": 2000}),
                (200, {}),  # resume
                (200, {}),  # controller
            ]
            status, body = handle_start_simulation("test-api-key")
        assert status == 200
        assert body["decision"] == "resumed_from_checkpoint"
        assert body["agents_spawned"] is False
        assert body["controller_activated"] is True
        assert body["simulation_started"] is True
        assert body["success"] is True

    def test_already_running(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "running", "drivers_total": 200, "riders_total": 2000}),
                (200, {}),  # controller
            ]
            status, body = handle_start_simulation("test-api-key")
        assert status == 200
        assert body["decision"] == "already_running"
        assert body["agents_spawned"] is False
        assert body["simulation_started"] is True

    def test_fresh_start_no_agents(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "stopped", "drivers_total": 0, "riders_total": 0}),
                (200, {}),  # /simulation/start
                (200, {}),  # immediate_drivers
                (200, {}),  # immediate_riders
                (200, {}),  # scheduled_drivers batch 1
                (200, {}),  # scheduled_drivers batch 2
                (200, {}),  # scheduled_riders
                (200, {}),  # controller
            ]
            status, body = handle_start_simulation("test-api-key")
        assert status == 200
        assert body["decision"] == "fresh_start"
        assert body["agents_spawned"] is True
        assert "agents" in body
        assert body["simulation_started"] is True

    def test_start_with_existing_agents(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "stopped", "drivers_total": 200, "riders_total": 2000}),
                (200, {}),  # /simulation/start
                (200, {}),  # controller
            ]
            status, body = handle_start_simulation("test-api-key")
        assert status == 200
        assert body["decision"] == "started_with_existing_agents"
        assert body["agents_spawned"] is False
        assert body["simulation_started"] is True

    def test_draining_waits_then_resumes(self, mock_secrets: object) -> None:
        with (
            patch("handler._simulation_api_request") as mock_api,
            patch("handler.time.sleep"),
        ):
            mock_api.side_effect = [
                (200, {"state": "draining", "drivers_total": 200, "riders_total": 2000}),
                (200, {"state": "paused", "drivers_total": 200, "riders_total": 2000}),
                (200, {}),  # resume
                (200, {}),  # controller
            ]
            status, body = handle_start_simulation("test-api-key")
        assert status == 200
        assert body["decision"] == "resumed_after_drain"
        assert body["simulation_started"] is True

    def test_status_query_failure(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (502, {"message": "Failed to connect"}),
            ]
            status, body = handle_start_simulation("test-api-key")
        assert status == 502
        assert body["success"] is False
        assert mock_api.call_count == 1

    def test_controller_activation_failure_non_fatal(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "paused", "drivers_total": 200, "riders_total": 2000}),
                (200, {}),  # resume succeeds
                (502, {"message": "Controller unreachable"}),  # controller fails
            ]
            status, body = handle_start_simulation("test-api-key")
        assert status == 200
        assert body["success"] is True
        assert body["controller_activated"] is False

    def test_fresh_start_default_counts(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "stopped", "drivers_total": 0, "riders_total": 0}),
                (200, {}),  # /simulation/start
                (200, {}),  # immediate_drivers (50)
                (200, {}),  # immediate_riders (50)
                (200, {}),  # scheduled_drivers batch 1 (100)
                (200, {}),  # scheduled_drivers batch 2 (50)
                (200, {}),  # scheduled_riders (1950)
                (200, {}),  # controller
            ]
            status, body = handle_start_simulation("test-api-key")
        assert status == 200
        for key, default_count in SIMULATION_START_DEFAULTS.items():
            assert body["agents"][key]["queued"] == default_count

    def test_fresh_start_custom_counts(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "stopped", "drivers_total": 0, "riders_total": 0}),
                (200, {}),  # /simulation/start
                (200, {}),  # immediate_drivers (10)
                (200, {}),  # immediate_riders (5)
                (200, {}),  # scheduled_drivers batch 1 (100)
                (200, {}),  # scheduled_drivers batch 2 (50)
                (200, {}),  # scheduled_riders (1950)
                (200, {}),  # controller
            ]
            status, body = handle_start_simulation(
                "test-api-key", {"immediate_drivers": 10, "immediate_riders": 5}
            )
        assert status == 200
        assert body["agents"]["immediate_drivers"]["queued"] == 10
        assert body["agents"]["immediate_riders"]["queued"] == 5
        assert body["agents"]["scheduled_drivers"]["queued"] == 150
        assert body["agents"]["scheduled_riders"]["queued"] == 1950

    def test_fresh_start_driver_batching(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "stopped", "drivers_total": 0, "riders_total": 0}),
                (200, {}),  # /simulation/start
                (200, {}),  # immediate_drivers (50)
                (200, {}),  # immediate_riders (50)
                (200, {}),  # scheduled_drivers batch 1 (100)
                (200, {}),  # scheduled_drivers batch 2 (100)
                (200, {}),  # scheduled_drivers batch 3 (50) — but defaults are 150, so 2 batches
                (200, {}),  # scheduled_riders
                (200, {}),  # controller
            ]
            handle_start_simulation("test-api-key", {"scheduled_drivers": 150})
        driver_calls = [
            c
            for c in mock_api.call_args_list
            if len(c.args) >= 2 and "drivers?mode=scheduled" in str(c.args[1])
        ]
        assert len(driver_calls) == 2
        assert driver_calls[0].args[3] == {"count": 100}
        assert driver_calls[1].args[3] == {"count": 50}

    def test_routing_direct_invocation(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "running", "drivers_total": 200, "riders_total": 2000}),
                (200, {}),  # controller
            ]
            result = lambda_handler({"action": "start-simulation", "api_key": "test-api-key"}, {})
        assert result["simulation_started"] is True
        assert result["success"] is True

    def test_routing_function_url(self, mock_secrets: object) -> None:
        with patch("handler._simulation_api_request") as mock_api:
            mock_api.side_effect = [
                (200, {"state": "running", "drivers_total": 200, "riders_total": 2000}),
                (200, {}),  # controller
            ]
            result = lambda_handler(
                {
                    "body": json.dumps({"action": "start-simulation", "api_key": "test-api-key"}),
                    "requestContext": {},
                },
                {},
            )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["simulation_started"] is True


class TestMaskEvent:
    def test_masks_api_key(self) -> None:
        event = {"action": "validate", "api_key": "test-key-abcd"}
        masked = _mask_event(event)
        assert masked["api_key"] == "***abcd"
        assert masked["action"] == "validate"

    def test_masks_password(self) -> None:
        event = {"action": "visitor-login", "email": "a@b.com", "password": "supersecret"}
        masked = _mask_event(event)
        assert masked["password"] == "***cret"
        assert masked["email"] == "a@b.com"

    def test_masks_short_values(self) -> None:
        event = {"api_key": "ab", "password": "x"}
        masked = _mask_event(event)
        assert masked["api_key"] == "***"
        assert masked["password"] == "***"

    def test_masks_body_field(self) -> None:
        body = json.dumps({"action": "validate", "api_key": "long-secret-key"})
        event = {"body": body, "requestContext": {}}
        masked = _mask_event(event)
        parsed_body = json.loads(masked["body"])
        assert parsed_body["api_key"] == "***-key"
        assert parsed_body["action"] == "validate"

    def test_preserves_non_sensitive_fields(self) -> None:
        event = {"action": "status", "extra": "data"}
        masked = _mask_event(event)
        assert masked == {"action": "status", "extra": "data"}

    def test_does_not_modify_original(self) -> None:
        event = {"api_key": "secret-key-value"}
        _mask_event(event)
        assert event["api_key"] == "secret-key-value"


class TestLogResponse:
    def test_error_response(self, capsys: pytest.CaptureFixture[str]) -> None:
        _log_response("shrink-session", 400, {"error": "Cannot shrink below 0"})
        captured = json.loads(capsys.readouterr().out.strip())
        assert captured["level"] == "ERROR"
        assert captured["action"] == "shrink-session"
        assert captured["status"] == 400
        assert captured["error"] == "Cannot shrink below 0"

    def test_success_response(self, capsys: pytest.CaptureFixture[str]) -> None:
        _log_response("session-status", 200, {"active": True})
        captured = json.loads(capsys.readouterr().out.strip())
        assert captured["level"] == "INFO"
        assert captured["action"] == "session-status"
        assert captured["status"] == 200
        assert "error" not in captured


class TestDispatcherLogging:
    def test_missing_action_logs(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Direct invocation with missing action emits structured log."""
        result = lambda_handler({"api_key": "some-key"}, {})
        assert result["error"] == "Missing required field: action"
        output = capsys.readouterr().out
        # Find the structured log line (not the event dump line)
        log_lines = [line for line in output.strip().split("\n") if '"level"' in line]
        assert len(log_lines) >= 1
        log_entry = json.loads(log_lines[0])
        assert log_entry["level"] == "ERROR"
        assert log_entry["action"] == "unknown"

    def test_missing_api_key_logs(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Direct invocation with missing api_key emits structured log."""
        result = lambda_handler({"action": "validate"}, {})
        assert result["error"] == "Missing required field: api_key"
        output = capsys.readouterr().out
        log_lines = [line for line in output.strip().split("\n") if '"level"' in line]
        assert len(log_lines) >= 1
        log_entry = json.loads(log_lines[0])
        assert log_entry["level"] == "ERROR"
        assert log_entry["action"] == "validate"

    def test_function_url_missing_action_logs(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Function URL invocation with missing action emits structured log."""
        event = {"body": json.dumps({"api_key": "some-key"}), "requestContext": {"http": {}}}
        result = lambda_handler(event, {})
        assert result["statusCode"] == 400
        output = capsys.readouterr().out
        log_lines = [line for line in output.strip().split("\n") if '"level"' in line]
        assert len(log_lines) >= 1
        log_entry = json.loads(log_lines[0])
        assert log_entry["level"] == "ERROR"
        assert log_entry["error"] == "Missing required field: action"
