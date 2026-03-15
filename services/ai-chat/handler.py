"""AI chat Lambda handler implementing action-based routing on a Lambda Function URL.

Two actions are supported:
- create-chat-session: Creates a new chat session, returning {session_id}.
- send-chat-message: Processes a user message through the LLM pipeline.

Invocation formats:
- Function URL: event contains HTTP metadata and body as a JSON string.
  Returns a full HTTP response dict {statusCode, headers, body}.
- Direct invocation: event contains action field at top level (used by LocalStack).
  Returns the business response dict directly.

Module dependencies (session, analytics, budget, starter_cache, llm_adapter) are
imported with try/except ImportError so the handler is independently testable with
unittest.mock.patch.
"""

import json
import logging
import os
import pathlib
import types
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level imports with stubs for isolated testing.
# Tests patch these via patch('handler.session'), etc.
# ---------------------------------------------------------------------------

try:
    import session
except ImportError:
    session = types.ModuleType("session")

try:
    import analytics
except ImportError:
    analytics = types.ModuleType("analytics")

try:
    import budget
except ImportError:
    budget = types.ModuleType("budget")

try:
    import starter_cache
except ImportError:
    starter_cache = types.ModuleType("starter_cache")

try:
    import llm_adapter
except ImportError:
    llm_adapter = types.ModuleType("llm_adapter")

try:
    import prompt_config
except ImportError:
    prompt_config = types.ModuleType("prompt_config")

try:
    import _secrets
except ImportError:
    _secrets = types.ModuleType("_secrets")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_MESSAGE_LENGTH = 1000
TURN_LIMIT = 20
DOCS_FILENAME = "AI-CHAT-CONTEXT.md"

# ---------------------------------------------------------------------------
# LLMResponse dataclass (mirrors the real module's type for type safety)
# ---------------------------------------------------------------------------


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    text: str
    input_tokens: int
    output_tokens: int
    cached: bool


# ---------------------------------------------------------------------------
# System prompt (module-level cache)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT: str | None = None


def _build_system_prompt() -> str:
    """Load and cache the system prompt from docs/AI-CHAT-CONTEXT.md.

    The docs file lives alongside handler.py at:
        <lambda_package>/docs/AI-CHAT-CONTEXT.md

    The content is wrapped in <documentation> XML tags.

    Returns:
        System prompt string ready to pass to the LLM provider.
    """
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is not None:
        return _SYSTEM_PROMPT

    docs_path = pathlib.Path(__file__).parent / "docs" / DOCS_FILENAME
    docs_content = docs_path.read_text(encoding="utf-8")
    prefix = getattr(prompt_config, "PROMPT_PREFIX", "")
    _SYSTEM_PROMPT = f"{prefix}\n<documentation>\n{docs_content}\n</documentation>"
    return _SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _get_response_headers() -> dict[str, str]:
    """Return standard response headers for Function URL responses.

    CORS headers are handled by AWS Lambda Function URL configuration
    (defined in Terraform).  Adding them here would duplicate header
    values, which browsers reject.

    Returns:
        Dict of non-CORS response headers.
    """
    return {"Content-Type": "application/json"}


def _http_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """Wrap a body dict in a Lambda Function URL HTTP envelope.

    Args:
        status_code: HTTP status code.
        body: Response payload to JSON-serialize.

    Returns:
        Lambda Function URL response dict.
    """
    return {
        "statusCode": status_code,
        "headers": _get_response_headers(),
        "body": json.dumps(body),
    }


def _error_response(status_code: int, error_code: str, message: str) -> dict[str, Any]:
    """Build a Function URL error response.

    Args:
        status_code: HTTP status code.
        error_code: Machine-readable error code (e.g. EMPTY_MESSAGE).
        message: Human-readable description.

    Returns:
        Lambda Function URL error response dict.
    """
    return _http_response(status_code, {"error": error_code, "message": message})


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


_PRICING: dict[str, tuple[float, float]] = {
    "anthropic": (3.0, 15.0),
    "openai": (0.40, 1.60),
    "google": (0.15, 0.60),
    "deepseek": (0.27, 1.10),
}


def _estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate LLM call cost in USD from token counts.

    Uses per-provider pricing (input $/M, output $/M).

    Args:
        provider: LLM provider name for pricing lookup.
        input_tokens: Number of input/prompt tokens consumed.
        output_tokens: Number of output/completion tokens generated.

    Returns:
        Estimated cost in USD.
    """
    input_rate, output_rate = _PRICING.get(provider, (3.0, 15.0))
    input_cost = input_tokens * input_rate / 1_000_000
    output_cost = output_tokens * output_rate / 1_000_000
    return input_cost + output_cost


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


def _handle_list_providers() -> dict[str, Any]:
    """Handle the list-providers action.

    Returns:
        Dict with a ``providers`` list, each entry having ``name`` and ``default`` fields.
    """
    available = _secrets.get_available_providers()
    default = os.environ.get("LLM_PROVIDER", "google")
    return {"providers": [{"name": p, "default": p == default} for p in available if p != "mock"]}


def _handle_create_chat_session(body: dict[str, Any]) -> dict[str, Any]:
    """Handle the create-chat-session action.

    Args:
        body: Parsed request payload. May contain optional 'visitor_email'.

    Returns:
        Business dict {session_id: str}.
    """
    visitor_email: str | None = body.get("visitor_email")
    bucket = os.environ.get("AI_CHAT_BUCKET", "")
    session_id: str = session.create_session(bucket=bucket, visitor_email=visitor_email)
    return {"session_id": session_id}


def _handle_send_chat_message(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Handle the send-chat-message action.

    Implements the full send-message flow:
    1. Validate message (empty / too long).
    2. Load session (404 if None).
    3. Check turn limit (>= 20 -> 400).
    4. Check budget (True -> 429).
    5. Check starter cache (if hit, skip LLM).
    6. Call LLM with system prompt.
    7. Update session.
    8. Log analytics.
    9. Return {response, turn_number}.

    Args:
        body: Parsed request payload.

    Returns:
        Tuple of (http_status_code, response_body_dict).
    """
    message: str = body.get("message", "")
    session_id: str = body.get("session_id", "")
    bucket = os.environ.get("AI_CHAT_BUCKET", "")
    daily_budget = float(os.environ.get("DAILY_BUDGET_USD", "5.00"))
    llm_provider_name = os.environ.get("LLM_PROVIDER", "google")

    # Resolve provider: request body overrides env var default
    requested_provider: str = body.get("provider", "")
    if requested_provider:
        available = _secrets.get_available_providers()
        if requested_provider not in available:
            return 400, {
                "error": "INVALID_PROVIDER",
                "message": f"Provider '{requested_provider}' is not available.",
            }
        resolved_provider = requested_provider
    else:
        resolved_provider = llm_provider_name

    # 1. Validate message
    if not message or not message.strip():
        return 400, {"error": "EMPTY_MESSAGE", "message": "Message must not be empty."}

    if len(message) > MAX_MESSAGE_LENGTH:
        return 400, {
            "error": "MESSAGE_TOO_LONG",
            "message": f"Message must not exceed {MAX_MESSAGE_LENGTH} characters.",
        }

    # 2. Load session
    session_data: dict[str, Any] | None = session.get_session(bucket=bucket, session_id=session_id)
    if session_data is None:
        return 404, {
            "error": "INVALID_SESSION",
            "message": f"Session '{session_id}' not found.",
        }

    # 3. Check turn limit
    turn_number: int = session_data.get("turn_number", 0)
    if turn_number >= TURN_LIMIT:
        return 400, {
            "error": "TURN_LIMIT_EXCEEDED",
            "message": f"Session has reached the maximum of {TURN_LIMIT} turns.",
        }

    # 4. Check budget
    budget_exceeded: bool = budget.check_budget(bucket=bucket, daily_budget_usd=daily_budget)
    if budget_exceeded:
        return 429, {
            "error": "BUDGET_EXCEEDED",
            "message": "Daily budget has been exceeded. Please try again tomorrow.",
        }

    new_turn_number = turn_number + 1
    response_text: str

    # 5. Check starter cache (only for default provider)
    default_provider = os.environ.get("LLM_PROVIDER", "anthropic")
    cached_response: str | None = None
    if resolved_provider == default_provider:
        cached_response = starter_cache.get_cached_response(message=message)
    if cached_response is not None:
        response_text = cached_response
        input_tokens = 0
        output_tokens = 0
        cost = 0.0
        llm_was_called = False
    else:
        # 6. Call LLM with system prompt
        try:
            system_prompt = _build_system_prompt()
            provider = llm_adapter.get_provider(provider=resolved_provider, model="")
            messages = list(session_data.get("messages", []))
            messages.append({"role": "user", "content": message})
            llm_resp = provider.complete(system_prompt=system_prompt, messages=messages)
        except Exception as exc:
            logger.exception("LLM call failed")
            return 502, {
                "error": "LLM_ERROR",
                "message": f"LLM provider returned an error: {exc}",
            }

        response_text = llm_resp.text
        input_tokens = llm_resp.input_tokens
        output_tokens = llm_resp.output_tokens
        cost = _estimate_cost(resolved_provider, input_tokens, output_tokens)
        llm_was_called = True

    # 7. Update session
    session.update_session(
        bucket=bucket,
        session_id=session_id,
        user_message=message,
        assistant_message=response_text,
        turn_number=new_turn_number,
    )

    # 8. Log analytics
    analytics.log_turn(
        bucket=bucket,
        session_id=session_id,
        turn_number=new_turn_number,
        user_message=message,
        assistant_message=response_text,
        input_tokens=input_tokens if llm_was_called else 0,
        output_tokens=output_tokens if llm_was_called else 0,
        cost_usd=cost if llm_was_called else 0.0,
        from_cache=not llm_was_called,
        provider=resolved_provider,
    )

    # 9. Return response
    return 200, {
        "response": response_text,
        "turn_number": new_turn_number,
        "provider": resolved_provider,
    }


# ---------------------------------------------------------------------------
# Lambda entrypoint
# ---------------------------------------------------------------------------


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Lambda function handler for AI chat actions.

    Supports two invocation formats:
    - Direct invocation: 'action' is a top-level field in the event.
      Returns the business response dict directly (no HTTP envelope).
      Used by LocalStack /invocations endpoint in local development.
    - Function URL invocation: event contains HTTP metadata; the request body
      is a JSON string under event['body'].
      Returns a full HTTP response dict {statusCode, headers, body}.

    Args:
        event: Lambda event from Function URL or direct invocation.
        context: Lambda context object (unused).

    Returns:
        Response dict whose format depends on invocation type.
    """
    print(f"Received event: {json.dumps(event)}")

    # ------------------------------------------------------------------
    # Direct invocation path: action field is top-level in the event.
    # Return business dict without an HTTP envelope.
    # ------------------------------------------------------------------
    if "action" in event:
        action: str = event["action"]

        if action == "create-chat-session":
            return _handle_create_chat_session(event)

        if action == "send-chat-message":
            status_code, body = _handle_send_chat_message(event)
            return body

        if action == "list-providers":
            return _handle_list_providers()

        # Unknown action — return error dict (no HTTP envelope)
        return {"error": "UNKNOWN_ACTION", "message": f"Unknown action: '{action}'"}

    # ------------------------------------------------------------------
    # Function URL path: parse body JSON and return HTTP envelope.
    # ------------------------------------------------------------------
    try:
        body_str = event.get("body", "{}")
        body = json.loads(body_str)
    except json.JSONDecodeError as exc:
        return _error_response(400, "INTERNAL_ERROR", f"Invalid JSON body: {exc}")

    action_str: str = body.get("action", "")

    try:
        if action_str == "create-chat-session":
            result = _handle_create_chat_session(body)
            return _http_response(200, result)

        if action_str == "send-chat-message":
            status_code, response_body = _handle_send_chat_message(body)
            return _http_response(status_code, response_body)

        if action_str == "list-providers":
            result = _handle_list_providers()
            return _http_response(200, result)

        return _error_response(400, "UNKNOWN_ACTION", f"Unknown action: '{action_str}'")

    except Exception as exc:
        logger.exception("Unhandled exception in lambda_handler")
        return _error_response(500, "INTERNAL_ERROR", f"Internal server error: {exc}")
