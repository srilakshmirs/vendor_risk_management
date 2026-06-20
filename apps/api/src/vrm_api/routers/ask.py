"""/ask — streaming RAG endpoint + a sync variant + reindex trigger.

The streaming endpoint emits Server-Sent Events:
    event: citations  → {"chunks": [{vendor_id, similarity, chunk}, ...]}
    event: token      → "raw text delta"
    event: done       → {"ok": true, "tokens_estimate": N}

Frontend consumes these via EventSource. Citations are sent first so the UI
can render the source panel immediately while tokens stream.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm import get_llm
from ..logging_config import get_logger
from ..rag.indexer import reindex_all
from ..rag.prompts import ASK_SYSTEM_PROMPT, build_user_prompt
from ..rag.retriever import RetrievedChunk, retrieve_top_k

router = APIRouter(prefix="/ask", tags=["ask"])
log = get_logger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    k: int = Field(8, ge=1, le=20)


class CitationOut(BaseModel):
    vendor_id: str
    similarity: float
    chunk: str


class AskSyncOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    model: str
    provider: str


class ReindexOut(BaseModel):
    status: str
    vendors: int
    chunks: int


# ── Helpers ───────────────────────────────────────────────────────────
def _serialise_citations(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {"vendor_id": c.entity_id, "similarity": c.similarity, "chunk": c.chunk}
        for c in chunks
    ]


# ── Endpoints ─────────────────────────────────────────────────────────
@router.post("/stream")
async def ask_stream(req: AskRequest, db: Session = Depends(get_db)):
    """SSE stream — emits citations event then token deltas, then done."""
    chunks = retrieve_top_k(db, req.question, k=req.k)
    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No embeddings found. Run `POST /ask/reindex` (or `make ask-reindex`) first.",
        )
    log.info("ask_retrieved", q=req.question[:60], hits=len(chunks))

    user_prompt = build_user_prompt(req.question, chunks)
    provider = get_llm()

    async def event_gen() -> AsyncIterator[dict]:
        # 1) citations payload up-front
        yield {
            "event": "citations",
            "data": json.dumps({"chunks": _serialise_citations(chunks)}),
        }

        # 2) stream LLM tokens
        token_count = 0
        try:
            async for delta in provider.stream(
                system=ASK_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=900,
                temperature=0.2,
                prefer_smart=True,
            ):
                token_count += 1
                yield {"event": "token", "data": delta}
                # gentle yield so the loop isn't CPU-starved
                if token_count % 16 == 0:
                    await asyncio.sleep(0)
        except Exception as exc:  # noqa: BLE001
            log.exception("ask_stream_error", error=str(exc))
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}
            return

        # 3) done event
        yield {
            "event": "done",
            "data": json.dumps({"ok": True, "tokens_estimate": token_count}),
        }

    return EventSourceResponse(event_gen())


@router.post("", response_model=AskSyncOut)
async def ask_sync(req: AskRequest, db: Session = Depends(get_db)) -> AskSyncOut:
    """Non-streaming variant — useful for tests, curl, and OpenAPI playground."""
    chunks = retrieve_top_k(db, req.question, k=req.k)
    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No embeddings found. Run `POST /ask/reindex` first.",
        )
    provider = get_llm()
    user_prompt = build_user_prompt(req.question, chunks)
    resp = await provider.complete(
        system=ASK_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=900,
        temperature=0.2,
        prefer_smart=True,
    )
    return AskSyncOut(
        answer=resp.text,
        citations=[CitationOut(**c) for c in _serialise_citations(chunks)],
        model=resp.model,
        provider=resp.provider,
    )


@router.post("/reindex", response_model=ReindexOut)
def ask_reindex(background: BackgroundTasks, async_mode: bool = False) -> ReindexOut:
    """Rebuild the embeddings table for every vendor."""
    if async_mode:
        background.add_task(reindex_all)
        return ReindexOut(status="queued", vendors=0, chunks=0)
    counts = reindex_all()
    return ReindexOut(status="complete", **counts)
