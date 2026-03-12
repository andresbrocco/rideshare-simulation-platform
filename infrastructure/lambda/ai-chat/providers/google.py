"""Google Gemini provider adapter.

Uses the ``google-genai`` SDK (``google.genai``).  The system prompt is passed
as ``system_instruction`` inside ``GenerateContentConfig`` rather than as a
conversation message, which is the native pattern for Gemini models.

The ``cached`` flag is set when ``usage_metadata.cached_content_token_count > 0``.
"""

import os

from google import genai
from google.genai import types

from _secrets import get_llm_api_key
from llm_adapter import LLMProvider, LLMResponse

_DEFAULT_MODEL = "gemini-2.5-flash"


class Provider(LLMProvider):
    """Google Gemini provider using the google-genai SDK.

    Args:
        model: Gemini model identifier.  Defaults to ``gemini-2.5-flash`` when
            the ``LLM_MODEL`` environment variable is not set.
    """

    def __init__(self, model: str = "") -> None:
        self._model = model

    def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        """Send a conversation to Google Gemini and return the reply.

        Converts the message list to ``types.Content`` objects required by the
        SDK.  The system prompt is provided via ``GenerateContentConfig`` so
        Gemini treats it as a system instruction, separate from user turns.

        Args:
            system_prompt: Instructions passed as the system instruction.
            messages: Ordered conversation history, each ``{"role": ..., "content": ...}``.

        Returns:
            LLMResponse with the assistant's reply and token counts.
        """
        model = self._model or os.environ.get("LLM_MODEL", _DEFAULT_MODEL)
        client = genai.Client(api_key=get_llm_api_key())

        genai_messages = [
            types.Content(
                role=m["role"],
                parts=[types.Part(text=m["content"])],
            )
            for m in messages
        ]

        response = client.models.generate_content(
            model=model,
            contents=genai_messages,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )

        usage = response.usage_metadata
        cached_tokens = getattr(usage, "cached_content_token_count", 0) or 0

        return LLMResponse(
            text=response.text or "",
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            cached=cached_tokens > 0,
        )
