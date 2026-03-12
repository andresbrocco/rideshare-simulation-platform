"""Tests for llm_adapter.py and providers/mock.py.

Covers:
- get_provider() factory (mock and unknown provider)
- MockProvider responses for all 4 starter questions
- MockProvider fallback for non-starter questions
- Multi-turn conversation routing (last user message wins)
- LLMResponse dataclass field types and equality
"""

import pytest

from llm_adapter import LLMProvider, LLMResponse, get_provider
from providers.mock import Provider as MockProvider


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestGetProvider:
    def test_get_provider_mock_returns_provider_instance(self) -> None:
        """get_provider('mock') returns a MockProvider that is a subclass of LLMProvider."""
        provider = get_provider(provider="mock")
        assert isinstance(provider, MockProvider)
        assert isinstance(provider, LLMProvider)

    def test_get_provider_unknown_raises_value_error(self) -> None:
        """get_provider with an unrecognised name raises ValueError mentioning the name."""
        with pytest.raises(ValueError, match="not-a-provider"):
            get_provider(provider="not-a-provider")


# ---------------------------------------------------------------------------
# MockProvider — starter question tests
# ---------------------------------------------------------------------------


class TestMockStarterResponses:
    """Verify each of the four starter questions returns a pre-written cached response."""

    def _provider(self) -> MockProvider:
        return MockProvider()

    def test_mock_starter_architecture(self) -> None:
        """'What is the architecture of this platform?' returns non-empty cached response."""
        p = self._provider()
        resp = p.complete(
            "sys",
            [{"role": "user", "content": "What is the architecture of this platform?"}],
        )
        assert isinstance(resp, LLMResponse)
        assert resp.text
        assert resp.cached is True
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0

    def test_mock_starter_simulation(self) -> None:
        """'How does the simulation engine work?' returns non-empty cached response."""
        p = self._provider()
        resp = p.complete(
            "sys",
            [{"role": "user", "content": "How does the simulation engine work?"}],
        )
        assert resp.text
        assert resp.cached is True

    def test_mock_starter_technologies(self) -> None:
        """'What technologies are used?' returns non-empty cached response."""
        p = self._provider()
        resp = p.complete(
            "sys",
            [{"role": "user", "content": "What technologies are used?"}],
        )
        assert resp.text
        assert resp.cached is True

    def test_mock_starter_data_flow(self) -> None:
        """'How does data flow through the system?' returns non-empty cached response."""
        p = self._provider()
        resp = p.complete(
            "sys",
            [{"role": "user", "content": "How does data flow through the system?"}],
        )
        assert resp.text
        assert resp.cached is True


# ---------------------------------------------------------------------------
# MockProvider — fallback test
# ---------------------------------------------------------------------------


class TestMockFallback:
    def test_mock_fallback_non_starter(self) -> None:
        """Non-starter question returns fallback with cached=False and zero token counts."""
        p = MockProvider()
        resp = p.complete(
            "sys",
            [{"role": "user", "content": "What is your favorite color?"}],
        )
        assert isinstance(resp, LLMResponse)
        assert resp.text
        assert resp.cached is False
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0


# ---------------------------------------------------------------------------
# MockProvider — multi-turn routing test
# ---------------------------------------------------------------------------


class TestMockMultiTurn:
    def test_mock_multi_turn_uses_last_user_message(self) -> None:
        """In a multi-turn conversation the last user message determines the response."""
        messages = [
            {"role": "user", "content": "What technologies are used?"},
            {"role": "assistant", "content": "Here are the technologies..."},
            {"role": "user", "content": "How does the simulation engine work?"},
        ]
        p = MockProvider()
        resp = p.complete("sys", messages)
        # Last user message is the simulation question → should be a starter response
        assert resp.cached is True
        assert resp.text
        # Confirm it is the simulation-specific answer, not the technology one
        assert "SimPy" in resp.text


# ---------------------------------------------------------------------------
# LLMResponse dataclass tests
# ---------------------------------------------------------------------------


class TestLLMResponseDataclass:
    def test_llm_response_fields_accessible(self) -> None:
        """LLMResponse fields are accessible and dataclass equality works."""
        resp = LLMResponse(text="hello", input_tokens=10, output_tokens=5, cached=False)
        assert resp.text == "hello"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5
        assert resp.cached is False

        # Dataclass equality
        resp2 = LLMResponse(text="hello", input_tokens=10, output_tokens=5, cached=False)
        assert resp == resp2

        resp3 = LLMResponse(text="different", input_tokens=10, output_tokens=5, cached=False)
        assert resp != resp3
