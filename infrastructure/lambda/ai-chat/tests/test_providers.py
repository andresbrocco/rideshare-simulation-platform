"""Unit tests for the four real LLM provider adapters.

Tests cover:
- Anthropic: cache_control sent on system prompt, cached flag on cache hit/miss,
  token count extraction
- OpenAI: cached flag from prompt_tokens_details.cached_tokens, missing details path
- DeepSeek: custom base_url, cached flag from prompt_cache_hit_tokens
- Google: cached flag from cached_content_token_count, token extraction
- All providers: return LLMResponse with correct field types
- Secrets Manager: module-level key cache (called only once across warm invocations)
"""

from typing import Any
from unittest.mock import MagicMock, patch

from anthropic.types import TextBlock

from llm_adapter import LLMResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_anthropic_usage(
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_input_tokens = cache_read_input_tokens
    usage.cache_creation_input_tokens = cache_creation_input_tokens
    return usage


def _make_anthropic_response(
    text: str = "Hello from Claude",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_read_input_tokens: int = 0,
) -> MagicMock:
    # Use a real TextBlock so isinstance(block, TextBlock) works in the adapter.
    content_block = TextBlock(type="text", text=text)

    response = MagicMock()
    response.content = [content_block]
    response.usage = _make_anthropic_usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
    )
    return response


def _make_openai_usage(
    prompt_tokens: int = 120,
    completion_tokens: int = 60,
    cached_tokens: int = 0,
    include_details: bool = True,
) -> MagicMock:
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    if include_details and cached_tokens is not None:
        details = MagicMock()
        details.cached_tokens = cached_tokens
        usage.prompt_tokens_details = details
    else:
        usage.prompt_tokens_details = None
    return usage


def _make_openai_response(
    text: str = "Hello from OpenAI",
    prompt_tokens: int = 120,
    completion_tokens: int = 60,
    cached_tokens: int = 0,
    include_details: bool = True,
) -> MagicMock:
    choice = MagicMock()
    choice.message.content = text

    response = MagicMock()
    response.choices = [choice]
    response.usage = _make_openai_usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        include_details=include_details,
    )
    return response


def _make_deepseek_usage(
    prompt_tokens: int = 80,
    completion_tokens: int = 40,
    prompt_cache_hit_tokens: int = 0,
) -> MagicMock:
    usage = MagicMock(spec=[])
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.prompt_cache_hit_tokens = prompt_cache_hit_tokens
    return usage


def _make_deepseek_response(
    text: str = "Hello from DeepSeek",
    prompt_tokens: int = 80,
    completion_tokens: int = 40,
    prompt_cache_hit_tokens: int = 0,
) -> MagicMock:
    choice = MagicMock()
    choice.message.content = text

    response = MagicMock()
    response.choices = [choice]
    response.usage = _make_deepseek_usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        prompt_cache_hit_tokens=prompt_cache_hit_tokens,
    )
    return response


def _make_google_usage_metadata(
    prompt_token_count: int = 200,
    candidates_token_count: int = 80,
    cached_content_token_count: int = 0,
) -> MagicMock:
    meta = MagicMock(spec=[])
    meta.prompt_token_count = prompt_token_count
    meta.candidates_token_count = candidates_token_count
    meta.cached_content_token_count = cached_content_token_count
    return meta


def _make_google_response(
    text: str = "Hello from Gemini",
    prompt_token_count: int = 200,
    candidates_token_count: int = 80,
    cached_content_token_count: int = 0,
) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.usage_metadata = _make_google_usage_metadata(
        prompt_token_count=prompt_token_count,
        candidates_token_count=candidates_token_count,
        cached_content_token_count=cached_content_token_count,
    )
    return response


# ---------------------------------------------------------------------------
# Anthropic provider tests
# ---------------------------------------------------------------------------


class TestAnthropicProvider:
    """Tests for providers/anthropic.py."""

    def _call_complete(
        self,
        mock_response: Any,
        system: str = "You are helpful.",
        messages: list[dict[str, str]] | None = None,
    ) -> tuple[LLMResponse, MagicMock]:
        """Call Provider.complete with a mocked SDK client, return (response, mock_client)."""
        if messages is None:
            messages = [{"role": "user", "content": "Hi"}]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with (
            patch("providers.anthropic.get_llm_api_key", return_value="test-key"),
            patch("providers.anthropic.anthropic.Anthropic", return_value=mock_client),
        ):
            from providers.anthropic import Provider

            result = Provider().complete(system, messages)

        return result, mock_client

    def test_cached_true_on_cache_hit(self) -> None:
        """cached=True when cache_read_input_tokens > 0."""
        mock_resp = _make_anthropic_response(cache_read_input_tokens=28000)
        result, _ = self._call_complete(mock_resp)
        assert result.cached is True

    def test_cached_false_on_cache_miss(self) -> None:
        """cached=False when cache_read_input_tokens == 0."""
        mock_resp = _make_anthropic_response(cache_read_input_tokens=0)
        result, _ = self._call_complete(mock_resp)
        assert result.cached is False

    def test_extracts_token_counts(self) -> None:
        """input_tokens and output_tokens are copied from usage."""
        mock_resp = _make_anthropic_response(input_tokens=150, output_tokens=75)
        result, _ = self._call_complete(mock_resp)
        assert result.input_tokens == 150
        assert result.output_tokens == 75

    def test_sends_cache_control_on_system_prompt(self) -> None:
        """messages.create is called with cache_control ephemeral on the system block."""
        mock_resp = _make_anthropic_response()
        _, mock_client = self._call_complete(mock_resp, system="Be concise.")

        create_call = mock_client.messages.create.call_args
        system_arg = create_call.kwargs["system"]

        assert isinstance(system_arg, list)
        assert len(system_arg) == 1
        block = system_arg[0]
        assert block["type"] == "text"
        assert block["text"] == "Be concise."
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_returns_llm_response_type(self) -> None:
        """complete() always returns an LLMResponse instance."""
        mock_resp = _make_anthropic_response(text="Reply")
        result, _ = self._call_complete(mock_resp)
        assert isinstance(result, LLMResponse)
        assert result.text == "Reply"

    def test_cache_read_none_treated_as_zero(self) -> None:
        """getattr fallback handles None cache_read_input_tokens gracefully."""
        mock_resp = _make_anthropic_response()
        # Simulate None returned by the usage attribute
        mock_resp.usage.cache_read_input_tokens = None
        result, _ = self._call_complete(mock_resp)
        assert result.cached is False

    def test_api_key_passed_to_client(self) -> None:
        """The API key from get_llm_api_key() is forwarded to anthropic.Anthropic."""
        mock_resp = _make_anthropic_response()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp

        with (
            patch("providers.anthropic.get_llm_api_key", return_value="sk-ant-secret"),
            patch("providers.anthropic.anthropic.Anthropic", return_value=mock_client) as mock_cls,
        ):
            from providers.anthropic import Provider

            Provider().complete("sys", [{"role": "user", "content": "hi"}])

        mock_cls.assert_called_once_with(api_key="sk-ant-secret")


# ---------------------------------------------------------------------------
# OpenAI provider tests
# ---------------------------------------------------------------------------


class TestOpenAIProvider:
    """Tests for providers/openai.py."""

    def _call_complete(
        self,
        mock_response: Any,
        system: str = "You are helpful.",
        messages: list[dict[str, str]] | None = None,
    ) -> tuple[LLMResponse, MagicMock]:
        if messages is None:
            messages = [{"role": "user", "content": "Hello"}]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with (
            patch("providers.openai.get_llm_api_key", return_value="test-key"),
            patch("providers.openai.openai.OpenAI", return_value=mock_client),
        ):
            from providers.openai import Provider

            result = Provider().complete(system, messages)

        return result, mock_client

    def test_cached_true_on_cache_hit(self) -> None:
        """cached=True when prompt_tokens_details.cached_tokens > 0."""
        mock_resp = _make_openai_response(cached_tokens=28000)
        result, _ = self._call_complete(mock_resp)
        assert result.cached is True

    def test_cached_false_when_no_cache(self) -> None:
        """cached=False when prompt_tokens_details is None."""
        mock_resp = _make_openai_response(include_details=False)
        result, _ = self._call_complete(mock_resp)
        assert result.cached is False

    def test_cached_false_when_cached_tokens_zero(self) -> None:
        """cached=False when cached_tokens == 0 (no cached content)."""
        mock_resp = _make_openai_response(cached_tokens=0)
        result, _ = self._call_complete(mock_resp)
        assert result.cached is False

    def test_extracts_token_counts(self) -> None:
        """prompt_tokens -> input_tokens, completion_tokens -> output_tokens."""
        mock_resp = _make_openai_response(prompt_tokens=200, completion_tokens=100)
        result, _ = self._call_complete(mock_resp)
        assert result.input_tokens == 200
        assert result.output_tokens == 100

    def test_system_prompt_prepended(self) -> None:
        """System prompt is sent as the first message with role='system'."""
        mock_resp = _make_openai_response()
        _, mock_client = self._call_complete(
            mock_resp,
            system="Act as a data engineer.",
            messages=[{"role": "user", "content": "Explain Kafka"}],
        )
        create_call = mock_client.chat.completions.create.call_args
        sent_messages = create_call.kwargs["messages"]
        assert sent_messages[0] == {"role": "system", "content": "Act as a data engineer."}
        assert sent_messages[1] == {"role": "user", "content": "Explain Kafka"}

    def test_returns_llm_response_type(self) -> None:
        """complete() always returns an LLMResponse instance."""
        mock_resp = _make_openai_response(text="GPT reply")
        result, _ = self._call_complete(mock_resp)
        assert isinstance(result, LLMResponse)
        assert result.text == "GPT reply"

    def test_none_message_content_returns_empty_string(self) -> None:
        """If message content is None the response text is an empty string."""
        mock_resp = _make_openai_response()
        mock_resp.choices[0].message.content = None
        result, _ = self._call_complete(mock_resp)
        assert result.text == ""


# ---------------------------------------------------------------------------
# DeepSeek provider tests
# ---------------------------------------------------------------------------


class TestDeepSeekProvider:
    """Tests for providers/deepseek.py."""

    def _call_complete(
        self,
        mock_response: Any,
        system: str = "You are helpful.",
        messages: list[dict[str, str]] | None = None,
    ) -> tuple[LLMResponse, MagicMock, MagicMock]:
        """Return (result, mock_client_instance, mock_OpenAI_class)."""
        if messages is None:
            messages = [{"role": "user", "content": "Hello"}]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with (
            patch("providers.deepseek.get_llm_api_key", return_value="test-key"),
            patch("providers.deepseek.openai.OpenAI", return_value=mock_client) as mock_cls,
        ):
            from providers.deepseek import Provider

            result = Provider().complete(system, messages)

        return result, mock_client, mock_cls

    def test_uses_custom_base_url(self) -> None:
        """openai.OpenAI is instantiated with base_url='https://api.deepseek.com'."""
        mock_resp = _make_deepseek_response()
        _, _, mock_cls = self._call_complete(mock_resp)
        mock_cls.assert_called_once()
        _, kwargs = mock_cls.call_args
        assert kwargs["base_url"] == "https://api.deepseek.com"

    def test_cached_true_on_cache_hit(self) -> None:
        """cached=True when prompt_cache_hit_tokens > 0."""
        mock_resp = _make_deepseek_response(prompt_cache_hit_tokens=15000)
        result, _, _ = self._call_complete(mock_resp)
        assert result.cached is True

    def test_cached_false_when_no_cache_hit(self) -> None:
        """cached=False when prompt_cache_hit_tokens == 0."""
        mock_resp = _make_deepseek_response(prompt_cache_hit_tokens=0)
        result, _, _ = self._call_complete(mock_resp)
        assert result.cached is False

    def test_extracts_token_counts(self) -> None:
        """prompt_tokens -> input_tokens, completion_tokens -> output_tokens."""
        mock_resp = _make_deepseek_response(prompt_tokens=90, completion_tokens=45)
        result, _, _ = self._call_complete(mock_resp)
        assert result.input_tokens == 90
        assert result.output_tokens == 45

    def test_returns_llm_response_type(self) -> None:
        """complete() always returns an LLMResponse instance."""
        mock_resp = _make_deepseek_response(text="DeepSeek says hi")
        result, _, _ = self._call_complete(mock_resp)
        assert isinstance(result, LLMResponse)
        assert result.text == "DeepSeek says hi"

    def test_system_prompt_prepended(self) -> None:
        """System prompt is sent as the first message with role='system'."""
        mock_resp = _make_deepseek_response()
        _, mock_client, _ = self._call_complete(
            mock_resp,
            system="You are a data engineer.",
            messages=[{"role": "user", "content": "What is Delta Lake?"}],
        )
        create_call = mock_client.chat.completions.create.call_args
        sent_messages = create_call.kwargs["messages"]
        assert sent_messages[0] == {"role": "system", "content": "You are a data engineer."}


# ---------------------------------------------------------------------------
# Google provider tests
# ---------------------------------------------------------------------------


class TestGoogleProvider:
    """Tests for providers/google.py."""

    def _call_complete(
        self,
        mock_response: Any,
        system: str = "You are helpful.",
        messages: list[dict[str, str]] | None = None,
    ) -> tuple[LLMResponse, MagicMock]:
        if messages is None:
            messages = [{"role": "user", "content": "Hello"}]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with (
            patch("providers.google.get_llm_api_key", return_value="test-key"),
            patch("providers.google.genai.Client", return_value=mock_client),
        ):
            from providers.google import Provider

            result = Provider().complete(system, messages)

        return result, mock_client

    def test_cached_true_on_cache_hit(self) -> None:
        """cached=True when cached_content_token_count > 0."""
        mock_resp = _make_google_response(cached_content_token_count=5000)
        result, _ = self._call_complete(mock_resp)
        assert result.cached is True

    def test_cached_false_when_no_cache(self) -> None:
        """cached=False when cached_content_token_count == 0."""
        mock_resp = _make_google_response(cached_content_token_count=0)
        result, _ = self._call_complete(mock_resp)
        assert result.cached is False

    def test_extracts_cached_content_tokens(self) -> None:
        """cached flag is driven by cached_content_token_count, not total tokens."""
        mock_resp = _make_google_response(
            prompt_token_count=300,
            candidates_token_count=100,
            cached_content_token_count=0,
        )
        result, _ = self._call_complete(mock_resp)
        assert result.cached is False
        assert result.input_tokens == 300
        assert result.output_tokens == 100

    def test_extracts_token_counts(self) -> None:
        """prompt_token_count -> input_tokens, candidates_token_count -> output_tokens."""
        mock_resp = _make_google_response(prompt_token_count=250, candidates_token_count=120)
        result, _ = self._call_complete(mock_resp)
        assert result.input_tokens == 250
        assert result.output_tokens == 120

    def test_returns_llm_response_type(self) -> None:
        """complete() always returns an LLMResponse instance."""
        mock_resp = _make_google_response(text="Gemini says hello")
        result, _ = self._call_complete(mock_resp)
        assert isinstance(result, LLMResponse)
        assert result.text == "Gemini says hello"

    def test_none_response_text_returns_empty_string(self) -> None:
        """If response.text is None the LLMResponse text is an empty string."""
        mock_resp = _make_google_response()
        mock_resp.text = None
        result, _ = self._call_complete(mock_resp)
        assert result.text == ""

    def test_missing_usage_metadata_fields_default_to_zero(self) -> None:
        """getattr fallbacks handle missing usage_metadata fields gracefully."""
        mock_resp = _make_google_response()
        # Remove the attributes entirely (spec=[] means getattr returns AttributeError)
        mock_resp.usage_metadata = MagicMock(spec=[])
        result, _ = self._call_complete(mock_resp)
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cached is False


# ---------------------------------------------------------------------------
# Cross-provider: all return LLMResponse
# ---------------------------------------------------------------------------


class TestAllProvidersReturnLLMResponse:
    """Verify every provider's complete() returns a properly-typed LLMResponse."""

    def test_all_providers_return_llm_response_type(self) -> None:
        """Each provider returns LLMResponse with int token counts and bool cached."""
        cases: list[tuple[str, Any]] = [
            ("providers.anthropic", _make_anthropic_response()),
            ("providers.openai", _make_openai_response()),
            ("providers.deepseek", _make_deepseek_response()),
            ("providers.google", _make_google_response()),
        ]

        for module_path, mock_resp in cases:
            module_name = module_path.split(".")[-1]

            mock_client = MagicMock()
            # Wire the mock client's completion method depending on provider
            if module_name == "anthropic":
                mock_client.messages.create.return_value = mock_resp
                client_patch = f"{module_path}.anthropic.Anthropic"
            elif module_name == "google":
                mock_client.models.generate_content.return_value = mock_resp
                client_patch = f"{module_path}.genai.Client"
            else:
                mock_client.chat.completions.create.return_value = mock_resp
                client_patch = f"{module_path}.openai.OpenAI"

            with (
                patch(f"{module_path}.get_llm_api_key", return_value="key"),
                patch(client_patch, return_value=mock_client),
            ):
                import importlib

                mod = importlib.import_module(module_path)
                provider = mod.Provider()
                result = provider.complete("sys", [{"role": "user", "content": "test"}])

            assert isinstance(result, LLMResponse), f"{module_name} did not return LLMResponse"
            assert isinstance(result.text, str), f"{module_name}: text must be str"
            assert isinstance(result.input_tokens, int), f"{module_name}: input_tokens must be int"
            assert isinstance(
                result.output_tokens, int
            ), f"{module_name}: output_tokens must be int"
            assert isinstance(result.cached, bool), f"{module_name}: cached must be bool"


# ---------------------------------------------------------------------------
# Secrets Manager module-level caching
# ---------------------------------------------------------------------------


class TestSecretsManagerCaching:
    """Verify get_llm_api_key() caches the keys after the first Secrets Manager call."""

    def test_secrets_manager_called_only_once(self) -> None:
        """Multiple calls to get_llm_api_key() hit Secrets Manager only once."""
        import _secrets

        # Reset the module-level cache to simulate a fresh container
        original = _secrets._LLM_API_KEYS
        _secrets._LLM_API_KEYS = None

        mock_sm_client = MagicMock()
        mock_sm_client.get_secret_value.return_value = {
            "SecretString": '{"anthropic": "cached-key-value", "openai": "other-key"}'
        }

        with patch("_secrets.boto3.client", return_value=mock_sm_client):
            key1 = _secrets.get_llm_api_key("anthropic")
            key2 = _secrets.get_llm_api_key("anthropic")
            key3 = _secrets.get_llm_api_key("openai")

        assert key1 == key2 == "cached-key-value"
        assert key3 == "other-key"
        # Secrets Manager should only have been called once
        assert mock_sm_client.get_secret_value.call_count == 1

        # Restore original state
        _secrets._LLM_API_KEYS = original
