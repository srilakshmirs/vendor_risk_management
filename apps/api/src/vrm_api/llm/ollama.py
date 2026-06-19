"""Local Ollama provider — talks to the daemon (default :11434).

Default model: llama3.2 (per user's local install). Works fully offline; ideal
for development without burning Anthropic credits, and as a fallback when no
API key is configured.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .base import LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout_s: float = 180.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        prefer_smart: bool = False,  # Ollama has one model in this deployment
    ) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(
            text=data["message"]["content"],
            model=self._model,
            provider=self.name,
            usage={
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
            raw=data,
        )

    async def extract_json(
        self,
        system: str,
        user: str,
        schema_hint: str,
        *,
        max_tokens: int = 2048,
        prefer_smart: bool = False,
    ) -> dict[str, Any]:
        # Ollama supports `format: json` natively — much more reliable than prompt-only.
        payload = {
            "model": self._model,
            "format": "json",
            "messages": [
                {"role": "system", "content": f"{system}\n\nSchema (return as JSON object):\n{schema_hint}"},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": max_tokens},
        }
        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return _parse_json(data["message"]["content"])

    async def stream(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        prefer_smart: bool = False,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = chunk.get("message") or {}
                if (text := msg.get("content")):
                    yield text
                if chunk.get("done"):
                    break


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)
