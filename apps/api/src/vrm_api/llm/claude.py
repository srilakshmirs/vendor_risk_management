"""Anthropic Claude provider — Haiku 4.5 for high-volume, Sonnet 4.6 for narratives.

Uses prompt-cache (ephemeral) on the system prompt so the per-vendor delta is the
only billed input on subsequent calls within the 5-minute window.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from .base import LLMProvider, LLMResponse


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(
        self,
        api_key: str,
        model_fast: str = "claude-haiku-4-5-20251001",
        model_smart: str = "claude-sonnet-4-6",
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model_fast = model_fast
        self._model_smart = model_smart

    def _model(self, prefer_smart: bool) -> str:
        return self._model_smart if prefer_smart else self._model_fast

    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        prefer_smart: bool = False,
    ) -> LLMResponse:
        model = self._model(prefer_smart)
        resp = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=[
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        usage = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0),
        }
        return LLMResponse(text=text, model=model, provider=self.name, usage=usage)

    async def extract_json(
        self,
        system: str,
        user: str,
        schema_hint: str,
        *,
        max_tokens: int = 2048,
        prefer_smart: bool = False,
    ) -> dict[str, Any]:
        sys = (
            f"{system}\n\n"
            f"Respond with a single JSON object — no prose, no markdown fences.\n"
            f"Schema:\n{schema_hint}"
        )
        resp = await self.complete(sys, user, max_tokens=max_tokens, temperature=0.0, prefer_smart=prefer_smart)
        return _parse_json(resp.text)

    async def stream(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        prefer_smart: bool = False,
    ) -> AsyncIterator[str]:
        model = self._model(prefer_smart)
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        ) as stream:
            async for text in stream.text_stream:
                yield text


def _parse_json(text: str) -> dict[str, Any]:
    """Best-effort JSON parsing — strips markdown fences if the model added them."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)
