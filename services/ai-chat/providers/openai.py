"""OpenAI provider adapter.

Uses the ``openai`` SDK with automatic prompt caching.  OpenAI caches prompts
that exceed 1,024 tokens automatically — no special configuration is required.

The ``cached`` flag is set when ``usage.prompt_tokens_details.cached_tokens > 0``.
"""

import openai
from openai.types.chat import ChatCompletionMessageParam

from _secrets import get_llm_api_key
from llm_adapter import LLMProvider, LLMResponse

_DEFAULT_MODEL = "gpt-4.1-mini"


class Provider(LLMProvider):
    """OpenAI provider with automatic prompt caching.

    Args:
        model: OpenAI model identifier.  Defaults to ``gpt-4.1-mini``.
    """

    def __init__(self, model: str = "") -> None:
        self._model = model

    def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        """Send a conversation to OpenAI and return the reply.

        Prepends the system prompt as a ``system`` role message.  Caching is
        handled automatically by OpenAI for prompts over 1,024 tokens.

        Args:
            system_prompt: Instructions prepended to the conversation.
            messages: Ordered conversation history, each ``{"role": ..., "content": ...}``.

        Returns:
            LLMResponse with the assistant's reply and token counts.
        """
        model = self._model or _DEFAULT_MODEL
        client = openai.OpenAI(api_key=get_llm_api_key("openai"))

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
        response = client.chat.completions.create(
            model=model, messages=all_messages, max_tokens=900
        )

        usage = response.usage
        cached_tokens = 0
        if usage and usage.prompt_tokens_details:
            cached_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0

        return LLMResponse(
            text=response.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            cached=cached_tokens > 0,
        )
