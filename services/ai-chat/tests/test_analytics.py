"""Unit tests for analytics.py — fire-and-forget JSONL analytics logging to S3.

Tests cover:
- log_turn writes to the correct S3 key prefix (analytics/{year}/{month}/*.jsonl)
- The S3 body is valid JSON terminated with a newline, containing all record fields
- Consecutive calls generate unique S3 keys (UUID-based)
- S3 ClientError is swallowed and logged via print()
- Any exception (e.g. malformed input) is swallowed and never re-raised
- Cached response fields are preserved correctly in the written record

Boto3 is mocked at the module level so no real AWS calls are made.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import analytics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client_error(code: str) -> ClientError:
    """Build a ClientError with the given error code."""
    return ClientError(
        error_response={"Error": {"Code": code, "Message": f"Simulated {code}"}},
        operation_name="PutObject",
    )


def _default_kwargs(
    bucket: str = "test-bucket",
    session_id: str = "abc-123",
    turn_number: int = 1,
    user_message: str = "How does the event-driven architecture work?",
    assistant_message: str = "The platform uses an event-driven approach...",
    input_tokens: int = 31200,
    output_tokens: int = 340,
    cost_usd: float = 0.08,
    from_cache: bool = False,
    has_visitor_email: bool = True,
) -> dict:
    return dict(
        bucket=bucket,
        session_id=session_id,
        turn_number=turn_number,
        user_message=user_message,
        assistant_message=assistant_message,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        from_cache=from_cache,
        has_visitor_email=has_visitor_email,
    )


# ---------------------------------------------------------------------------
# Key format tests
# ---------------------------------------------------------------------------


class TestLogTurnKeyFormat:
    def test_log_turn_writes_to_correct_prefix(self) -> None:
        """Key starts with analytics/{year}/{month}/ and ends with .jsonl."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        with patch("analytics._get_s3_client", return_value=mock_client):
            analytics.log_turn(**_default_kwargs())

        call_kwargs = mock_client.put_object.call_args.kwargs
        key: str = call_kwargs["Key"]

        # Key must follow analytics/YYYY/MM/<uuid>.jsonl
        parts = key.split("/")
        assert parts[0] == "analytics"
        assert len(parts[1]) == 4 and parts[1].isdigit(), f"Year segment invalid: {parts[1]}"
        assert len(parts[2]) == 2 and parts[2].isdigit(), f"Month segment invalid: {parts[2]}"
        assert parts[3].endswith(".jsonl"), f"Filename must end with .jsonl: {parts[3]}"

    def test_log_turn_unique_key_per_call(self) -> None:
        """Two consecutive calls produce different S3 keys (UUID-based)."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        kwargs = _default_kwargs()
        with patch("analytics._get_s3_client", return_value=mock_client):
            analytics.log_turn(**kwargs)
            analytics.log_turn(**kwargs)

        assert mock_client.put_object.call_count == 2
        first_key = mock_client.put_object.call_args_list[0].kwargs["Key"]
        second_key = mock_client.put_object.call_args_list[1].kwargs["Key"]
        assert first_key != second_key


# ---------------------------------------------------------------------------
# Body format tests
# ---------------------------------------------------------------------------


class TestLogTurnBodyFormat:
    def test_log_turn_body_is_valid_jsonl(self) -> None:
        """Body is valid JSON terminated with a newline and contains all record fields."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        kwargs = _default_kwargs()
        with patch("analytics._get_s3_client", return_value=mock_client):
            analytics.log_turn(**kwargs)

        call_kwargs = mock_client.put_object.call_args.kwargs
        body: str = call_kwargs["Body"]

        assert body.endswith("\n"), "Body must be terminated with a newline"
        record = json.loads(body.strip())

        assert "timestamp" in record
        assert record["session_id"] == "abc-123"
        assert record["turn_number"] == 1
        assert record["question"] == "How does the event-driven architecture work?"
        assert record["response"] == "The platform uses an event-driven approach..."
        assert record["input_tokens"] == 31200
        assert record["output_tokens"] == 340
        assert record["cost_usd"] == pytest.approx(0.08)
        assert record["cached"] is False
        assert record["has_visitor_email"] is True

    def test_log_turn_content_type_is_ndjson(self) -> None:
        """ContentType is set to application/x-ndjson."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        with patch("analytics._get_s3_client", return_value=mock_client):
            analytics.log_turn(**_default_kwargs())

        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["ContentType"] == "application/x-ndjson"

    def test_log_turn_writes_to_correct_bucket(self) -> None:
        """Bucket parameter is forwarded to put_object."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        with patch("analytics._get_s3_client", return_value=mock_client):
            analytics.log_turn(**_default_kwargs(bucket="my-analytics-bucket"))

        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "my-analytics-bucket"


# ---------------------------------------------------------------------------
# Error-swallowing tests
# ---------------------------------------------------------------------------


class TestLogTurnErrorHandling:
    def test_log_turn_swallows_s3_client_error(self) -> None:
        """ClientError from put_object is caught; no exception propagates."""
        mock_client = MagicMock()
        mock_client.put_object.side_effect = _make_client_error("AccessDenied")
        with patch("analytics._get_s3_client", return_value=mock_client):
            # Must not raise
            analytics.log_turn(**_default_kwargs())

    def test_log_turn_swallows_s3_client_error_prints_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A failed S3 write logs to stdout (CloudWatch) and does not raise."""
        mock_client = MagicMock()
        mock_client.put_object.side_effect = _make_client_error("ServiceUnavailable")
        with patch("analytics._get_s3_client", return_value=mock_client):
            analytics.log_turn(**_default_kwargs())

        captured = capsys.readouterr()
        assert "Analytics write failed" in captured.out

    def test_log_turn_swallows_any_exception(self) -> None:
        """An unexpected exception inside log_turn never propagates to the caller."""
        with patch("analytics._get_s3_client", side_effect=RuntimeError("unexpected")):
            # Must not raise
            analytics.log_turn(**_default_kwargs())

    def test_log_turn_does_not_raise_on_missing_env(self) -> None:
        """log_turn works even when LLM_MODEL env var is absent."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        import os

        env_without_model = {k: v for k, v in os.environ.items() if k != "LLM_MODEL"}
        with (
            patch("analytics._get_s3_client", return_value=mock_client),
            patch.dict(os.environ, env_without_model, clear=True),
        ):
            analytics.log_turn(**_default_kwargs())


# ---------------------------------------------------------------------------
# Cached response tests
# ---------------------------------------------------------------------------


class TestLogTurnCachedResponse:
    def test_log_turn_cached_response_fields(self) -> None:
        """Cached response fields are preserved verbatim in the written record."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        with patch("analytics._get_s3_client", return_value=mock_client):
            analytics.log_turn(
                **_default_kwargs(
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    from_cache=True,
                )
            )

        call_kwargs = mock_client.put_object.call_args.kwargs
        record = json.loads(call_kwargs["Body"].strip())

        assert record["model"] == "cache"
        assert record["input_tokens"] == 0
        assert record["output_tokens"] == 0
        assert record["cost_usd"] == pytest.approx(0.0)
        assert record["cached"] is True

    def test_log_turn_non_cached_model_name(self) -> None:
        """Non-cached responses use the provider parameter as the model field."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}

        with patch("analytics._get_s3_client", return_value=mock_client):
            analytics.log_turn(**_default_kwargs(from_cache=False), provider="anthropic")

        call_kwargs = mock_client.put_object.call_args.kwargs
        record = json.loads(call_kwargs["Body"].strip())
        assert record["model"] == "anthropic"
        assert record["provider"] == "anthropic"
        assert record["cached"] is False
