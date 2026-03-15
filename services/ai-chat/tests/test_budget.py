"""Unit tests for budget.py — daily cost cap enforcement via S3 counter.

Tests cover:
- check_budget returns False when no counter exists (first call of the day)
- check_budget returns False when accumulated cost is under the daily limit
- check_budget returns True when accumulated cost equals the daily limit
- check_budget returns True when accumulated cost exceeds the daily limit
- check_budget propagates non-404 ClientErrors to the caller
- update_budget creates a new counter when none exists yet
- update_budget increments an existing counter (cost and request count)
- update_budget uses today's date in the S3 key
- The counter schema contains the expected fields (date, total_cost_usd, total_requests)

Boto3 is mocked at the module level so no real AWS calls are made.
"""

import json
import re
from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import budget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client_error(code: str) -> ClientError:
    """Build a ClientError with the given error code."""
    return ClientError(
        error_response={"Error": {"Code": code, "Message": f"Simulated {code}"}},
        operation_name="GetObject",
    )


def _make_mock_body(data: dict[str, Any]) -> MagicMock:
    """Return a mock response Body whose .read() returns serialised JSON bytes."""
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps(data).encode("utf-8")
    return mock_body


def _counter(total_cost_usd: float, total_requests: int = 1) -> dict[str, Any]:
    """Build a minimal counter dict for use in get_object mock responses."""
    return {
        "date": date.today().isoformat(),
        "total_cost_usd": total_cost_usd,
        "total_requests": total_requests,
    }


# ---------------------------------------------------------------------------
# check_budget tests
# ---------------------------------------------------------------------------


class TestCheckBudget:
    def test_check_budget_returns_false_when_no_counter(self) -> None:
        """check_budget returns False (no spending today) when the counter key is absent."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        with patch("budget._get_s3_client", return_value=mock_client):
            result = budget.check_budget("test-bucket", 5.00)

        assert result is False

    def test_check_budget_returns_false_when_under_limit(self) -> None:
        """check_budget returns False when total_cost_usd is below the daily limit."""
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(_counter(3.42))}
        with patch("budget._get_s3_client", return_value=mock_client):
            result = budget.check_budget("test-bucket", 5.00)

        assert result is False

    def test_check_budget_returns_true_when_at_limit(self) -> None:
        """check_budget returns True when total_cost_usd exactly equals the daily limit."""
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(_counter(5.00))}
        with patch("budget._get_s3_client", return_value=mock_client):
            result = budget.check_budget("test-bucket", 5.00)

        assert result is True

    def test_check_budget_returns_true_when_over_limit(self) -> None:
        """check_budget returns True when total_cost_usd exceeds the daily limit."""
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(_counter(5.18))}
        with patch("budget._get_s3_client", return_value=mock_client):
            result = budget.check_budget("test-bucket", 5.00)

        assert result is True

    def test_check_budget_propagates_non_404_errors(self) -> None:
        """Non-404 ClientErrors (e.g. AccessDenied) propagate to the caller unchanged."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("AccessDenied")
        with patch("budget._get_s3_client", return_value=mock_client):
            with pytest.raises(ClientError) as exc_info:
                budget.check_budget("test-bucket", 5.00)

        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    def test_check_budget_404_code_treated_as_missing(self) -> None:
        """Numeric 404 error code is also treated as a missing counter."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("404")
        with patch("budget._get_s3_client", return_value=mock_client):
            result = budget.check_budget("test-bucket", 5.00)

        assert result is False


# ---------------------------------------------------------------------------
# update_budget tests
# ---------------------------------------------------------------------------


class TestUpdateBudget:
    def test_update_budget_creates_counter_when_missing(self) -> None:
        """update_budget creates a new counter with the supplied cost when none exists."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        mock_client.put_object.return_value = {}
        with patch("budget._get_s3_client", return_value=mock_client):
            budget.update_budget("test-bucket", 0.08)

        call_kwargs = mock_client.put_object.call_args.kwargs
        written = json.loads(call_kwargs["Body"])
        assert pytest.approx(written["total_cost_usd"], rel=1e-6) == 0.08
        assert written["total_requests"] == 1

    def test_update_budget_increments_existing_counter(self) -> None:
        """update_budget adds the new cost to an existing total and bumps request count."""
        existing = {"date": date.today().isoformat(), "total_cost_usd": 3.42, "total_requests": 38}
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(existing)}
        mock_client.put_object.return_value = {}
        with patch("budget._get_s3_client", return_value=mock_client):
            budget.update_budget("test-bucket", 0.08)

        call_kwargs = mock_client.put_object.call_args.kwargs
        written = json.loads(call_kwargs["Body"])
        assert pytest.approx(written["total_cost_usd"], rel=1e-6) == 3.50
        assert written["total_requests"] == 39

    def test_update_budget_uses_today_date_in_key(self) -> None:
        """update_budget writes to a key containing today's ISO date."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        mock_client.put_object.return_value = {}
        with patch("budget._get_s3_client", return_value=mock_client):
            budget.update_budget("test-bucket", 0.01)

        call_kwargs = mock_client.put_object.call_args.kwargs
        key: str = call_kwargs["Key"]

        today_str = date.today().isoformat()
        assert key == f"budget/{today_str}-counter.json"

    def test_update_budget_key_matches_pattern(self) -> None:
        """update_budget key matches the budget/YYYY-MM-DD-counter.json pattern."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        mock_client.put_object.return_value = {}
        with patch("budget._get_s3_client", return_value=mock_client):
            budget.update_budget("test-bucket", 0.01)

        call_kwargs = mock_client.put_object.call_args.kwargs
        key: str = call_kwargs["Key"]
        assert re.match(
            r"^budget/\d{4}-\d{2}-\d{2}-counter\.json$", key
        ), f"Key did not match expected pattern: {key!r}"

    def test_update_budget_counter_schema(self) -> None:
        """Written counter contains the expected schema fields."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        mock_client.put_object.return_value = {}
        with patch("budget._get_s3_client", return_value=mock_client):
            budget.update_budget("test-bucket", 0.05)

        call_kwargs = mock_client.put_object.call_args.kwargs
        written = json.loads(call_kwargs["Body"])

        assert "date" in written
        assert "total_cost_usd" in written
        assert "total_requests" in written
        # date field should be today's ISO date string
        assert written["date"] == date.today().isoformat()

    def test_update_budget_content_type_is_json(self) -> None:
        """update_budget sets ContentType to application/json on put_object."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        mock_client.put_object.return_value = {}
        with patch("budget._get_s3_client", return_value=mock_client):
            budget.update_budget("test-bucket", 0.05)

        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["ContentType"] == "application/json"

    def test_update_budget_writes_to_correct_bucket(self) -> None:
        """update_budget forwards the bucket name to put_object."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        mock_client.put_object.return_value = {}
        with patch("budget._get_s3_client", return_value=mock_client):
            budget.update_budget("my-budget-bucket", 0.05)

        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "my-budget-bucket"


# ---------------------------------------------------------------------------
# LocalStack endpoint tests
# ---------------------------------------------------------------------------


class TestLocalStackEndpoint:
    def test_s3_client_uses_localstack_endpoint_when_env_set(self) -> None:
        """_get_s3_client uses a LocalStack endpoint when LOCALSTACK_HOSTNAME is set."""
        import os

        with (
            patch.dict(os.environ, {"LOCALSTACK_HOSTNAME": "localstack"}),
            patch("budget.boto3") as mock_boto3,
        ):
            mock_boto3.client.return_value = MagicMock()
            budget._get_s3_client()

        _, kwargs = mock_boto3.client.call_args
        assert kwargs["endpoint_url"] == "http://localstack:4566"

    def test_s3_client_no_localstack_endpoint_when_env_absent(self) -> None:
        """_get_s3_client uses no endpoint_url when LOCALSTACK_HOSTNAME is absent."""
        import os

        env_without_localstack = {k: v for k, v in os.environ.items() if k != "LOCALSTACK_HOSTNAME"}
        with (
            patch.dict(os.environ, env_without_localstack, clear=True),
            patch("budget.boto3") as mock_boto3,
        ):
            mock_boto3.client.return_value = MagicMock()
            budget._get_s3_client()

        _, kwargs = mock_boto3.client.call_args
        assert kwargs["endpoint_url"] is None
