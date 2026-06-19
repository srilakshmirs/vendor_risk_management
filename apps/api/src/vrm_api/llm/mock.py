"""Canned responses — lets the entire stack run with zero API key + zero Ollama.

Useful for CI, unit tests, and the moment a judge clones your repo and you
haven't shared your API key.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from .base import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self) -> None:
        self._model = "mock-1"

    async def complete(self, system, user, *, max_tokens=1024, temperature=0.0, prefer_smart=False):
        text = (
            "Risk narrative (MOCK): based on the vendor profile, "
            "elevated risk is driven by certification gaps and recent breach signals. "
            "Recommended action: rotate credentials, request updated SOC 2 report, "
            "and notify procurement of contract status."
        )
        return LLMResponse(text=text, model=self._model, provider=self.name, usage={"input_tokens": 0, "output_tokens": 0})

    async def extract_json(self, system, user, schema_hint, *, max_tokens=2048, prefer_smart=False) -> dict[str, Any]:
        # Returns a plausible contract-extraction payload
        return {
            "parties": ["Société Générale", "Vendor (mock)"],
            "data_access": ["PII", "Internal"],
            "sla_uptime_pct": 99.5,
            "breach_notification_hours": 72,
            "indemnification_cap_usd": 1_000_000,
            "auto_renew": False,
            "term_months": 24,
            "_meta": {"source": "mock"},
        }

    async def stream(self, system, user, *, max_tokens=1024, temperature=0.2, prefer_smart=False) -> AsyncIterator[str]:
        for chunk in [
            "This vendor ", "has elevated risk ", "due to ", "compliance gaps ",
            "and a recent ", "breach event. ", "Recommended action: ", "review access scope.",
        ]:
            yield chunk
