"""Quick endpoint to verify which LLM the API is talking to right now."""

from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..llm import get_llm
from ..schemas.common import LLMInfoOut

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/info", response_model=LLMInfoOut)
async def llm_info() -> LLMInfoOut:
    """Reports the active provider and runs a 1-word health probe."""
    provider = get_llm()
    model = ""
    available = False
    detail: str | None = None
    try:
        resp = await provider.complete(
            system="You answer with a single word.",
            user="Reply with the word: ready",
            max_tokens=8,
            temperature=0.0,
        )
        model = resp.model
        available = True
        detail = resp.text.strip()[:64]
    except Exception as exc:  # noqa: BLE001
        model = settings.ollama_model if provider.name == "ollama" else settings.claude_model_fast
        available = False
        detail = f"{type(exc).__name__}: {exc}"[:200]
    return LLMInfoOut(provider=provider.name, model=model, available=available, detail=detail)
