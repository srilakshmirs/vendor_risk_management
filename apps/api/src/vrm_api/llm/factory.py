"""Provider selection. One env var (LLM_PROVIDER) decides which backend runs."""

from __future__ import annotations

from ..config import settings
from ..logging_config import get_logger
from .base import LLMProvider
from .claude import ClaudeProvider
from .mock import MockProvider
from .ollama import OllamaProvider

log = get_logger(__name__)
_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    """Singleton accessor — first call constructs the provider, rest reuse it."""
    global _provider
    if _provider is not None:
        return _provider

    choice = settings.llm_provider
    if choice == "claude":
        if not settings.anthropic_api_key:
            log.warning("LLM_PROVIDER=claude but ANTHROPIC_API_KEY is empty — falling back to mock")
            _provider = MockProvider()
        else:
            _provider = ClaudeProvider(
                api_key=settings.anthropic_api_key,
                model_fast=settings.claude_model_fast,
                model_smart=settings.claude_model_smart,
            )
    elif choice == "ollama":
        _provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    elif choice == "mock":
        _provider = MockProvider()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {choice!r}")

    log.info("llm_provider_initialised", provider=_provider.name)
    return _provider


def reset_llm() -> None:
    """Test hook — clears the singleton so tests can swap providers."""
    global _provider
    _provider = None
