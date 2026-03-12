"""DeepSeek provider adapter.

Uses the ``openai`` SDK pointed at DeepSeek's API endpoint via ``base_url``.
DeepSeek's API is OpenAI-compatible, so the same SDK works for both.

DeepSeek returns ``prompt_cache_hit_tokens`` inside the usage object (a
non-standard extension to the OpenAI response schema).  The ``cached`` flag
is set when that field is greater than zero.
"""

import os

import openai
from openai.types.chat import ChatCompletionMessageParam

from _secrets import get_llm_api_key
from llm_adapter import LLMProvider, LLMResponse

_DEFAULT_MODEL = "deepseek-chat"
_BASE_URL = "https://api.deepseek.com"


class Provider(LLMProvider):
    """DeepSeek provider using the OpenAI SDK with a custom base URL.

    Args:
        model: DeepSeek model identifier.  Defaults to ``deepseek-chat`` when
            the ``LLM_MODEL`` environment variable is not set.
    """

    def __init__(self, model: str = "") -> None:
        self._model = model

    def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        """Send a conversation to DeepSeek and return the reply.

        Connects to ``https://api.deepseek.com`` using the OpenAI SDK.
        Prepends the system prompt as a ``system`` role message.  DeepSeek's
        cache hit count is read from the non-standard ``prompt_cache_hit_tokens``
        field on the usage object.

        Args:
            system_prompt: Instructions prepended to the conversation.
            messages: Ordered conversation history, each ``{"role": ..., "content": ...}``.

        Returns:
            LLMResponse with the assistant's reply and token counts.
        """
        model = self._model or os.environ.get("LLM_MODEL", _DEFAULT_MODEL)
        client = openai.OpenAI(
            api_key=get_llm_api_key(),
            base_url=_BASE_URL,
        )

        all_messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
        ]
        for m in messages:
            # Each message has role "user" or "assistant"; cast to satisfy mypy.
            role = m["role"]
            if role == "user":
                all_messages.append({"role": "user", "content": m["content"]})
            else:
                all_messages.append({"role": "assistant", "content": m["content"]})
        response = client.chat.completions.create(model=model, messages=all_messages)

        usage = response.usage
        # DeepSeek extends OpenAI's usage schema with prompt_cache_hit_tokens
        cached_tokens = getattr(usage, "prompt_cache_hit_tokens", 0) or 0

        return LLMResponse(
            text=response.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            cached=cached_tokens > 0,
        )
