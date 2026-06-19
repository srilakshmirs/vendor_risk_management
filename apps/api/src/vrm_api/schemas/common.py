from __future__ import annotations

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str = "ok"
    environment: str
    version: str


class LLMInfoOut(BaseModel):
    provider: str
    model: str
    available: bool
    detail: str | None = None
