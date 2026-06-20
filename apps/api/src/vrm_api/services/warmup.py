"""Pre-warm the embedder + LLM so the first /ask request isn't a cold start.

Without this, the first request pays:
  * fastembed ONNX model load   (~1-3 s once cached, ~30 s on first download)
  * Ollama model load into VRAM (~5-15 s on first call after server restart)

We fire both as background asyncio tasks during FastAPI startup. The API
becomes reachable in <100 ms; warmup completes in parallel. If a request
lands before warmup finishes, it pays the cold-start as before — no harm done.

Disable via env: ``WARMUP_ON_STARTUP=false``.
"""

from __future__ import annotations

import asyncio
import time

from ..llm import get_llm
from ..logging_config import get_logger

log = get_logger(__name__)


async def warmup_embedder() -> None:
    """Load the fastembed ONNX model into memory (singleton; cached thereafter)."""
    t0 = time.perf_counter()
    try:
        loop = asyncio.get_event_loop()
        # Heavy synchronous load — push to default thread pool so the event
        # loop stays free to handle incoming requests in parallel.
        from ..rag.embedder import embed_one

        await loop.run_in_executor(None, embed_one, "warmup")
        log.info("embedder_warmed_up", duration_ms=int((time.perf_counter() - t0) * 1000))
    except Exception as exc:  # noqa: BLE001
        log.warning("embedder_warmup_failed", error=str(exc), duration_ms=int((time.perf_counter() - t0) * 1000))


async def warmup_llm() -> None:
    """Send a tiny prompt so Ollama loads the model into VRAM (or Claude opens a HTTP/2 connection)."""
    t0 = time.perf_counter()
    try:
        provider = get_llm()
        await provider.complete(
            system="Reply with one short word.",
            user="ready?",
            max_tokens=4,
            temperature=0.0,
        )
        log.info(
            "llm_warmed_up",
            provider=provider.name,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "llm_warmup_failed",
            error=str(exc),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )


async def warmup_all() -> dict[str, str]:
    """Run embedder + LLM warmups concurrently. Returns a summary dict for /healthz."""
    log.info("warmup_started")
    t0 = time.perf_counter()
    await asyncio.gather(warmup_embedder(), warmup_llm(), return_exceptions=True)
    log.info("warmup_complete", duration_ms=int((time.perf_counter() - t0) * 1000))
    return {"status": "ok", "duration_ms": str(int((time.perf_counter() - t0) * 1000))}
