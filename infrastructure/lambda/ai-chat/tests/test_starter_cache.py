"""Unit tests for starter_cache.py — S3-backed starter question response cache.

Tests cover:
- get_cached_response returns the cached response text for an exact question match
- get_cached_response returns None for a partial match or case-sensitive variation
- get_cached_response returns None when the cache has not been loaded
- load_cache reads the S3 object and stores responses in the module-level variable
- load_cache returns None when the cache file is missing (NoSuchKey / 404)
- load_cache is idempotent — warm invocations reuse the already-loaded data
- load_cache swallows unexpected S3 errors and returns None

Boto3 is mocked at the module level so no real AWS calls are made.
"""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import starter_cache


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


def _sample_cache_payload(
    responses: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a minimal valid cache JSON payload."""
    if responses is None:
        responses = {
            "What is the architecture of this platform?": "This platform uses a five-layer architecture...",
            "How does the simulation engine work?": "The simulation uses SimPy discrete-event...",
            "What technologies are used?": "The platform uses Python, Kafka, Delta Lake...",
            "How does data flow through the system?": "Data flows from the simulation via Kafka...",
        }
    return {
        "generated_at": "2026-03-12T00:00:00+00:00",
        "docs_hash": "sha256:abcdef1234567890",
        "responses": responses,
    }


# ---------------------------------------------------------------------------
# Fixture: reset module-level cache before each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_module_cache() -> None:
    """Reset starter_cache._CACHE to None before each test for isolation."""
    starter_cache._CACHE = None
    yield
    starter_cache._CACHE = None


# ---------------------------------------------------------------------------
# get_cached_response tests
# ---------------------------------------------------------------------------


class TestGetCachedResponse:
    def test_get_cached_response_returns_response_for_exact_match(self) -> None:
        """get_cached_response returns the stored text for an exact question match."""
        starter_cache._CACHE = _sample_cache_payload()
        question = "What is the architecture of this platform?"
        result = starter_cache.get_cached_response(question)
        assert result == "This platform uses a five-layer architecture..."

    def test_get_cached_response_returns_none_for_partial_match(self) -> None:
        """get_cached_response returns None when the question is a substring match only."""
        starter_cache._CACHE = _sample_cache_payload()
        result = starter_cache.get_cached_response("architecture of this platform")
        assert result is None

    def test_get_cached_response_returns_none_for_case_sensitive_variation(self) -> None:
        """get_cached_response returns None for a differently-cased version of the question."""
        starter_cache._CACHE = _sample_cache_payload()
        result = starter_cache.get_cached_response("what is the architecture of this platform?")
        assert result is None

    def test_get_cached_response_returns_none_when_cache_not_loaded(self) -> None:
        """get_cached_response returns None when _CACHE is None (cache not yet loaded)."""
        assert starter_cache._CACHE is None
        result = starter_cache.get_cached_response("What is the architecture of this platform?")
        assert result is None

    def test_get_cached_response_returns_none_for_unknown_question(self) -> None:
        """get_cached_response returns None for a question not present in the cache."""
        starter_cache._CACHE = _sample_cache_payload()
        result = starter_cache.get_cached_response("What is your favorite color?")
        assert result is None


# ---------------------------------------------------------------------------
# load_cache tests
# ---------------------------------------------------------------------------


class TestLoadCache:
    def test_load_cache_stores_data_from_s3(self) -> None:
        """load_cache reads the S3 object and populates the module-level _CACHE variable."""
        payload = _sample_cache_payload()
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(payload)}
        with patch("starter_cache._get_s3_client", return_value=mock_client):
            result = starter_cache.load_cache("test-bucket")

        assert result is not None
        assert starter_cache._CACHE is not None
        assert starter_cache._CACHE["docs_hash"] == "sha256:abcdef1234567890"
        assert "What is the architecture of this platform?" in starter_cache._CACHE["responses"]

    def test_load_cache_returns_payload_on_success(self) -> None:
        """load_cache returns the parsed cache dict when S3 read succeeds."""
        payload = _sample_cache_payload()
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(payload)}
        with patch("starter_cache._get_s3_client", return_value=mock_client):
            result = starter_cache.load_cache("test-bucket")

        assert result == payload

    def test_load_cache_returns_none_when_missing(self) -> None:
        """load_cache returns None when the cache file does not exist in S3 (NoSuchKey)."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        with patch("starter_cache._get_s3_client", return_value=mock_client):
            result = starter_cache.load_cache("test-bucket")

        assert result is None
        assert starter_cache._CACHE is None

    def test_load_cache_returns_none_when_404(self) -> None:
        """load_cache returns None for a numeric 404 error code (treated as missing)."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("404")
        with patch("starter_cache._get_s3_client", return_value=mock_client):
            result = starter_cache.load_cache("test-bucket")

        assert result is None

    def test_load_cache_idempotent_warm_invocations(self) -> None:
        """load_cache called a second time when _CACHE is already populated skips S3."""
        payload = _sample_cache_payload()
        starter_cache._CACHE = payload

        mock_client = MagicMock()
        with patch("starter_cache._get_s3_client", return_value=mock_client):
            result = starter_cache.load_cache("test-bucket")

        # S3 must not have been called on warm invocation
        mock_client.get_object.assert_not_called()
        assert result == payload

    def test_load_cache_swallows_unexpected_errors(self) -> None:
        """load_cache returns None and does not raise for unexpected S3 errors."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("InternalError")
        with patch("starter_cache._get_s3_client", return_value=mock_client):
            result = starter_cache.load_cache("test-bucket")

        assert result is None
        assert starter_cache._CACHE is None

    def test_load_cache_reads_correct_s3_key(self) -> None:
        """load_cache requests the cache/starter-responses.json key."""
        payload = _sample_cache_payload()
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": _make_mock_body(payload)}
        with patch("starter_cache._get_s3_client", return_value=mock_client):
            starter_cache.load_cache("my-bucket")

        call_kwargs = mock_client.get_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "my-bucket"
        assert call_kwargs["Key"] == "cache/starter-responses.json"
