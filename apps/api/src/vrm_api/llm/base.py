"""Provider-agnostic LLM interface.

Both Claude and Ollama implementations satisfy this protocol so the rest of the
codebase never branches on provider identity. Switching providers is a single
env-var flip (`LLM_PROVIDER=ollama` -> `LLM_PROVIDER=claude`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str


class LLMResponse(BaseModel):
    text: str
    model: str
    provider: str
    usage: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] | None = None


class LLMProvider(ABC):
    """Minimal async interface every provider must implement."""

    name: str

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        prefer_smart: bool = False,
    ) -> LLMResponse:
        """Single-turn completion. `prefer_smart=True` opts into the more capable model when available."""

    @abstractmethod
    async def extract_json(
        self,
        system: str,
        user: str,
        schema_hint: str,
        *,
        max_tokens: int = 2048,
        prefer_smart: bool = False,
    ) -> dict[str, Any]:
        """Force structured JSON output. `schema_hint` is appended to the system prompt."""

    @abstractmethod
    async def stream(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        prefer_smart: bool = False,
    ) -> AsyncIterator[str]:
        """Yield text deltas. Used for the 'Ask about vendor X' UI streaming."""

    async def aclose(self) -> None:
        """Optional cleanup hook (HTTP clients, etc.)."""
        return None
