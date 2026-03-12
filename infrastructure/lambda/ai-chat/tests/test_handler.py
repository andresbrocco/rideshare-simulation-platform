"""Tests for ai-chat Lambda handler action routing and validation.

Tests cover:
- create-chat-session action via Function URL and direct invocation
- send-chat-message validation (empty, whitespace, too long)
- send-chat-message error paths (invalid session, turn limit, budget exceeded)
- send-chat-message happy paths (cache hit, LLM success)
- Unknown action routing
"""

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch


import handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_function_url_event(body: dict[str, Any]) -> dict[str, Any]:
    """Wrap a body dict in a Lambda Function URL HTTP envelope."""
    return {"body": json.dumps(body)}


def _make_session(turn_number: int = 0) -> dict[str, Any]:
    return {
        "session_id": "test-session-id",
        "turn_number": turn_number,
        "messages": [],
        "visitor_email": None,
    }


def _make_llm_response(
    text: str = "Answer", input_tokens: int = 100, output_tokens: int = 50
) -> Any:
    """Create a mock LLMResponse-like object."""
    mock = MagicMock()
    mock.text = text
    mock.input_tokens = input_tokens
    mock.output_tokens = output_tokens
    mock.cached = False
    return mock


# ---------------------------------------------------------------------------
# create-chat-session tests
# ---------------------------------------------------------------------------


class TestCreateChatSession:
    def test_create_session_returns_session_id(self) -> None:
        """Function URL invocation returns {statusCode: 200, body: {session_id}}."""
        event = _make_function_url_event({"action": "create-chat-session"})
        with (
            patch("handler.session") as mock_session,
            patch.dict(os.environ, {"AI_CHAT_BUCKET": "test-bucket"}),
        ):
            mock_session.create_session.return_value = "test-uuid-1234"
            result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["session_id"] == "test-uuid-1234"
        assert "headers" in result
        assert result["headers"]["Content-Type"] == "application/json"

    def test_create_session_with_visitor_email(self) -> None:
        """create_session is called with visitor_email when provided."""
        event = _make_function_url_event(
            {"action": "create-chat-session", "visitor_email": "user@example.com"}
        )
        with (
            patch("handler.session") as mock_session,
            patch.dict(os.environ, {"AI_CHAT_BUCKET": "test-bucket"}),
        ):
            mock_session.create_session.return_value = "new-session-uuid"
            result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "session_id" in body
        mock_session.create_session.assert_called_once()
        call_kwargs = mock_session.create_session.call_args
        # visitor_email should be passed to create_session
        assert "user@example.com" in (str(call_kwargs.args) + str(call_kwargs.kwargs))


# ---------------------------------------------------------------------------
# send-chat-message validation tests
# ---------------------------------------------------------------------------


class TestSendMessageValidation:
    def test_send_message_empty_returns_400(self) -> None:
        """Empty message body returns 400 with EMPTY_MESSAGE error."""
        event = _make_function_url_event(
            {
                "action": "send-chat-message",
                "session_id": "abc",
                "message": "",
            }
        )
        result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "EMPTY_MESSAGE"
        assert "message" in body

    def test_send_message_whitespace_returns_400(self) -> None:
        """Whitespace-only message returns 400 with EMPTY_MESSAGE error."""
        event = _make_function_url_event(
            {
                "action": "send-chat-message",
                "session_id": "abc",
                "message": "   ",
            }
        )
        result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "EMPTY_MESSAGE"

    def test_send_message_too_long_returns_400(self) -> None:
        """Message exceeding 1000 characters returns 400 with MESSAGE_TOO_LONG error."""
        event = _make_function_url_event(
            {
                "action": "send-chat-message",
                "session_id": "abc",
                "message": "x" * 1001,
            }
        )
        result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "MESSAGE_TOO_LONG"


# ---------------------------------------------------------------------------
# send-chat-message error path tests
# ---------------------------------------------------------------------------


class TestSendMessageErrorPaths:
    def test_send_message_invalid_session_returns_404(self) -> None:
        """session.get_session returning None yields 404 INVALID_SESSION."""
        event = _make_function_url_event(
            {
                "action": "send-chat-message",
                "session_id": "nonexistent",
                "message": "Hello there",
            }
        )
        with (
            patch("handler.session") as mock_session,
            patch.dict(os.environ, {"AI_CHAT_BUCKET": "test-bucket"}),
        ):
            mock_session.get_session.return_value = None
            result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert body["error"] == "INVALID_SESSION"

    def test_send_message_turn_limit_exceeded_returns_400(self) -> None:
        """Session with turn_number >= 20 returns 400 TURN_LIMIT_EXCEEDED."""
        event = _make_function_url_event(
            {
                "action": "send-chat-message",
                "session_id": "valid-session",
                "message": "Another message",
            }
        )
        with (
            patch("handler.session") as mock_session,
            patch.dict(os.environ, {"AI_CHAT_BUCKET": "test-bucket"}),
        ):
            mock_session.get_session.return_value = _make_session(turn_number=20)
            result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "TURN_LIMIT_EXCEEDED"

    def test_send_message_budget_exceeded_returns_429(self) -> None:
        """budget.check_budget returning True yields 429 BUDGET_EXCEEDED."""
        event = _make_function_url_event(
            {
                "action": "send-chat-message",
                "session_id": "valid-session",
                "message": "How much does this cost?",
            }
        )
        with (
            patch("handler.session") as mock_session,
            patch("handler.budget") as mock_budget,
            patch.dict(
                os.environ,
                {"AI_CHAT_BUCKET": "test-bucket", "DAILY_BUDGET_USD": "5.00"},
            ),
        ):
            mock_session.get_session.return_value = _make_session(turn_number=0)
            mock_budget.check_budget.return_value = True
            result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 429
        body = json.loads(result["body"])
        assert body["error"] == "BUDGET_EXCEEDED"


# ---------------------------------------------------------------------------
# send-chat-message happy path tests
# ---------------------------------------------------------------------------


class TestSendMessageHappyPaths:
    def test_send_message_cache_hit_skips_llm(self) -> None:
        """Cache hit returns cached response without calling llm_adapter.get_provider."""
        event = _make_function_url_event(
            {
                "action": "send-chat-message",
                "session_id": "valid-session",
                "message": "What is the architecture of this platform?",
            }
        )
        with (
            patch("handler.session") as mock_session,
            patch("handler.budget") as mock_budget,
            patch("handler.starter_cache") as mock_cache,
            patch("handler.llm_adapter") as mock_llm,
            patch("handler.analytics"),
            patch.dict(os.environ, {"AI_CHAT_BUCKET": "test-bucket"}),
        ):
            mock_session.get_session.return_value = _make_session(turn_number=0)
            mock_budget.check_budget.return_value = False
            mock_cache.get_cached_response.return_value = "Cached answer"
            result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["response"] == "Cached answer"
        assert body["turn_number"] == 1
        mock_llm.get_provider.assert_not_called()

    def test_send_message_success_returns_response_and_turn_number(self) -> None:
        """Full LLM success path returns response text and incremented turn_number."""
        event = _make_function_url_event(
            {
                "action": "send-chat-message",
                "session_id": "valid-session",
                "message": "How does it work?",
            }
        )
        llm_response = _make_llm_response(text="Answer", input_tokens=100, output_tokens=50)
        mock_provider = MagicMock()
        mock_provider.complete.return_value = llm_response

        with (
            patch("handler.session") as mock_session,
            patch("handler.budget") as mock_budget,
            patch("handler.starter_cache") as mock_cache,
            patch("handler.llm_adapter") as mock_llm,
            patch("handler.analytics"),
            patch("handler._build_system_prompt", return_value="sys prompt"),
            patch.dict(
                os.environ,
                {"AI_CHAT_BUCKET": "test-bucket", "LLM_PROVIDER": "anthropic"},
            ),
        ):
            mock_session.get_session.return_value = _make_session(turn_number=0)
            mock_budget.check_budget.return_value = False
            mock_cache.get_cached_response.return_value = None
            mock_llm.get_provider.return_value = mock_provider
            result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["response"] == "Answer"
        assert body["turn_number"] == 1


# ---------------------------------------------------------------------------
# Direct invocation tests
# ---------------------------------------------------------------------------


class TestDirectInvocation:
    def test_direct_invocation_create_session(self) -> None:
        """Direct invocation event (no HTTP envelope) returns business dict without statusCode."""
        event: dict[str, Any] = {"action": "create-chat-session"}
        with (
            patch("handler.session") as mock_session,
            patch.dict(os.environ, {"AI_CHAT_BUCKET": "test-bucket"}),
        ):
            mock_session.create_session.return_value = "uuid-abc"
            result = handler.lambda_handler(event, None)

        assert "statusCode" not in result
        assert result["session_id"] == "uuid-abc"


# ---------------------------------------------------------------------------
# Unknown action tests
# ---------------------------------------------------------------------------


class TestUnknownAction:
    def test_unknown_action_returns_400(self) -> None:
        """Unrecognised action returns 400 with UNKNOWN_ACTION error code."""
        event = _make_function_url_event({"action": "unknown-action"})
        result = handler.lambda_handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "UNKNOWN_ACTION"
