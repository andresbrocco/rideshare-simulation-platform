"""Unit tests for session.py — S3-backed session state management.

Tests cover:
- create_session returns a valid UUID string
- create_session stores visitor_email in the written session JSON
- create_session initialises messages=[] and turn_number=0
- create_session propagates S3 errors to the caller
- get_session returns a parsed dict for existing sessions
- get_session returns None for missing keys (NoSuchKey / 404)
- get_session propagates non-404 ClientError exceptions
- update_session writes to the correct S3 key with the supplied data
- update_session propagates S3 errors to the caller

Boto3 is mocked at the module level so no real AWS calls are made.
"""

import json
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client_error(code: str) -> ClientError:
    """Build a ClientError with the given error code."""
    return ClientError(
        error_response={"Error": {"Code": code, "Message": f"Simulated {code}"}},
        operation_name="TestOperation",
    )


def _make_mock_body(data: dict[str, Any]) -> MagicMock:
    """Return a mock response Body whose .read() returns serialised JSON bytes."""
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps(data).encode("utf-8")
    return mock_body


# ---------------------------------------------------------------------------
# create_session tests
# ---------------------------------------------------------------------------


class TestCreateSession:
    def test_create_session_returns_uuid(self) -> None:
        """create_session returns a valid UUID4 string."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        with patch("session._get_s3_client", return_value=mock_client):
            result = session.create_session("test-bucket")

        # Must be parseable as a UUID
        parsed = uuid.UUID(result, version=4)
        assert str(parsed) == result

    def test_create_session_with_visitor_email(self) -> None:
        """create_session stores visitor_email in the session JSON written to S3."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        with patch("session._get_s3_client", return_value=mock_client):
            session.create_session("test-bucket", visitor_email="user@example.com")

        call_kwargs = mock_client.put_object.call_args.kwargs
        body = json.loads(call_kwargs["Body"])
        assert body["visitor_email"] == "user@example.com"

    def test_create_session_writes_empty_messages(self) -> None:
        """create_session initialises messages=[] and turn_number=0 in the written JSON."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        with patch("session._get_s3_client", return_value=mock_client):
            session.create_session("test-bucket")

        call_kwargs = mock_client.put_object.call_args.kwargs
        body = json.loads(call_kwargs["Body"])
        assert body["messages"] == []
        assert body["turn_number"] == 0

    def test_create_session_s3_error_raises(self) -> None:
        """S3 put_object failure propagates to the caller unchanged."""
        mock_client = MagicMock()
        mock_client.put_object.side_effect = _make_client_error("InternalError")
        with patch("session._get_s3_client", return_value=mock_client):
            with pytest.raises(ClientError):
                session.create_session("test-bucket")

    def test_create_session_writes_to_correct_key(self) -> None:
        """create_session uses the sessions/{uuid}.json key pattern."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        with patch("session._get_s3_client", return_value=mock_client):
            session_id = session.create_session("test-bucket")

        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["Key"] == f"sessions/{session_id}.json"
        assert call_kwargs["Bucket"] == "test-bucket"

    def test_create_session_writes_session_id_in_body(self) -> None:
        """The session_id field in the written JSON matches the returned UUID."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        with patch("session._get_s3_client", return_value=mock_client):
            returned_id = session.create_session("test-bucket")

        call_kwargs = mock_client.put_object.call_args.kwargs
        body = json.loads(call_kwargs["Body"])
        assert body["session_id"] == returned_id


# ---------------------------------------------------------------------------
# get_session tests
# ---------------------------------------------------------------------------


class TestGetSession:
    def test_get_session_returns_dict(self) -> None:
        """get_session parses and returns the session JSON stored in S3."""
        stored_data: dict[str, Any] = {
            "session_id": "abc-123",
            "visitor_email": None,
            "messages": [],
            "turn_number": 0,
            "created_at": "2026-03-11T10:00:00+00:00",
        }
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(stored_data)}
        with patch("session._get_s3_client", return_value=mock_client):
            result = session.get_session("test-bucket", "abc-123")

        assert result == stored_data

    def test_get_session_missing_key_returns_none(self) -> None:
        """NoSuchKey error from S3 is silently converted to None."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        with patch("session._get_s3_client", return_value=mock_client):
            result = session.get_session("test-bucket", "nonexistent-id")

        assert result is None

    def test_get_session_404_error_returns_none(self) -> None:
        """A 404 error code from S3 is also treated as a missing session."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("404")
        with patch("session._get_s3_client", return_value=mock_client):
            result = session.get_session("test-bucket", "nonexistent-id")

        assert result is None

    def test_get_session_other_error_raises(self) -> None:
        """Non-404 ClientErrors propagate to the caller unchanged."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("AccessDenied")
        with patch("session._get_s3_client", return_value=mock_client):
            with pytest.raises(ClientError) as exc_info:
                session.get_session("test-bucket", "some-id")

        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    def test_get_session_reads_correct_key(self) -> None:
        """get_session requests the sessions/{session_id}.json key."""
        stored_data: dict[str, Any] = {"session_id": "xyz"}
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(stored_data)}
        with patch("session._get_s3_client", return_value=mock_client):
            session.get_session("my-bucket", "xyz")

        call_kwargs = mock_client.get_object.call_args.kwargs
        assert call_kwargs["Key"] == "sessions/xyz.json"
        assert call_kwargs["Bucket"] == "my-bucket"


# ---------------------------------------------------------------------------
# update_session tests
# ---------------------------------------------------------------------------


class TestUpdateSession:
    def test_update_session_writes_to_s3(self) -> None:
        """update_session reads the session, appends messages, and writes back."""
        existing_data: dict[str, Any] = {
            "session_id": "abc-123",
            "visitor_email": None,
            "messages": [],
            "turn_number": 0,
            "created_at": "2026-03-11T10:00:00+00:00",
        }
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(existing_data)}
        mock_client.put_object.return_value = {}
        with patch("session._get_s3_client", return_value=mock_client):
            session.update_session(
                bucket="test-bucket",
                session_id="abc-123",
                user_message="Hello",
                assistant_message="Hi there!",
                turn_number=1,
            )

        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "sessions/abc-123.json"
        written_body = json.loads(call_kwargs["Body"])
        assert written_body["turn_number"] == 1
        assert written_body["messages"] == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

    def test_update_session_s3_error_raises(self) -> None:
        """S3 put_object failure propagates to the caller unchanged."""
        existing_data: dict[str, Any] = {
            "session_id": "abc-123",
            "messages": [],
            "turn_number": 0,
        }
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(existing_data)}
        mock_client.put_object.side_effect = _make_client_error("InternalError")
        with patch("session._get_s3_client", return_value=mock_client):
            with pytest.raises(ClientError):
                session.update_session(
                    bucket="test-bucket",
                    session_id="abc-123",
                    user_message="Hello",
                    assistant_message="Hi",
                    turn_number=1,
                )

    def test_update_session_creates_session_if_missing(self) -> None:
        """update_session creates a new session if the key is not found."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        mock_client.put_object.return_value = {}
        with patch("session._get_s3_client", return_value=mock_client):
            session.update_session(
                bucket="test-bucket",
                session_id="abc-123",
                user_message="Hello",
                assistant_message="Hi!",
                turn_number=1,
            )

        call_kwargs = mock_client.put_object.call_args.kwargs
        written_body = json.loads(call_kwargs["Body"])
        assert written_body["session_id"] == "abc-123"
        assert written_body["turn_number"] == 1
        assert len(written_body["messages"]) == 2
