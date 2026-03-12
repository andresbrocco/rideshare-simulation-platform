"""LLM provider abstraction layer for ai-chat Lambda.

Defines the LLMResponse dataclass, the abstract LLMProvider base class, and the
get_provider() factory that lazy-imports provider modules by name.

Supported provider names (each maps to providers/<name>.py):
- anthropic
- openai
- google
- deepseek
- mock

Usage::

    from llm_adapter import get_provider

    provider = get_provider(provider="mock", model="unused")
    response = provider.complete(system_prompt="...", messages=[...])
    print(response.text)
"""

import importlib
import types
from abc import ABC, abstractmethod
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

_SUPPORTED_PROVIDERS = ("anthropic", "openai", "google", "deepseek", "mock")


@dataclass
class LLMResponse:
    """Response returned by any LLM provider.

    Attributes:
        text: The assistant's reply text.
        input_tokens: Number of input/prompt tokens consumed (0 if unknown).
        output_tokens: Number of output/completion tokens generated (0 if unknown).
        cached: True if the response came from a local cache rather than a live LLM call.
    """

    text: str
    input_tokens: int
    output_tokens: int
    cached: bool


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.

    Each concrete provider lives in providers/<name>.py and must expose a
    class named ``Provider`` that subclasses ``LLMProvider``.

    Args:
        model: Model identifier string (e.g. ``"claude-3-5-sonnet-20241022"``).
            Concrete providers use this to select the specific model to call.
            The mock provider ignores it.
    """

    def __init__(self, model: str = "") -> None:
        self._model = model

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        """Send a conversation to the LLM and return its reply.

        Args:
            system_prompt: Instructions prepended before the conversation.
            messages: Ordered list of messages, each ``{"role": ..., "content": ...}``.
                      Roles are ``"user"`` or ``"assistant"``.

        Returns:
            LLMResponse with the model's reply and token accounting.
        """


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_provider(provider: str, model: str = "") -> LLMProvider:
    """Return an initialised LLMProvider for the given provider name.

    The provider module is lazy-imported on first call, so unused providers
    (and their heavyweight SDKs) are never loaded.

    Args:
        provider: Provider identifier string.  Must be one of
            ``anthropic``, ``openai``, ``google``, ``deepseek``, or ``mock``.
        model: Model name passed through to providers that need it.
            Ignored by the mock provider.

    Returns:
        A ready-to-use LLMProvider instance.

    Raises:
        ValueError: If ``provider`` is not a recognised provider name.
    """
    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. "
            f"Supported providers: {', '.join(_SUPPORTED_PROVIDERS)}"
        )

    module: types.ModuleType = importlib.import_module(f"providers.{provider}")
    provider_cls: type[LLMProvider] = module.Provider
    return provider_cls(model=model)
