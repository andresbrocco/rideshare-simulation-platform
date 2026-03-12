"""Anthropic Claude provider adapter.

Uses the ``anthropic`` SDK with native prompt caching (``cache_control:
ephemeral``) on the system prompt.  Anthropic caches system prompts for
5 minutes, so back-to-back turns in the same session hit the cache and
reduce input token cost by roughly 90%.

The ``cached`` flag is set when ``usage.cache_read_input_tokens > 0``.
"""

import os

import anthropic
from anthropic.types import MessageParam, TextBlock

from _secrets import get_llm_api_key
from llm_adapter import LLMProvider, LLMResponse

_DEFAULT_MODEL = "claude-sonnet-4-20250514"


class Provider(LLMProvider):
    """Anthropic Claude provider with prompt caching.

    Args:
        model: Anthropic model identifier.  Defaults to ``claude-sonnet-4-20250514``
            when the ``LLM_MODEL`` environment variable is not set.
    """

    def __init__(self, model: str = "") -> None:
        self._model = model

    def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        """Send a conversation to Anthropic Claude and return the reply.

        The system prompt is sent with ``cache_control: ephemeral`` so that
        Anthropic caches it across requests within the same 5-minute window.

        Args:
            system_prompt: Instructions prepended to the conversation.
            messages: Ordered conversation history, each ``{"role": ..., "content": ...}``.

        Returns:
            LLMResponse with the assistant's reply and token counts.
        """
        model = self._model or os.environ.get("LLM_MODEL", _DEFAULT_MODEL)
        client = anthropic.Anthropic(api_key=get_llm_api_key())

        # Cast to the SDK's typed param list so mypy is satisfied.
        typed_messages: list[MessageParam] = [
            {"role": m["role"], "content": m["content"]}  # type: ignore[typeddict-item]
            for m in messages
        ]

        response = client.messages.create(
            model=model,
            max_tokens=1500,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=typed_messages,
        )

        usage = response.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

        # response.content[0] is a TextBlock for standard completions; extract
        # the text safely so non-text block types don't cause an AttributeError.
        first_block = response.content[0]
        reply_text = first_block.text if isinstance(first_block, TextBlock) else ""

        return LLMResponse(
            text=reply_text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached=cache_read > 0,
        )
