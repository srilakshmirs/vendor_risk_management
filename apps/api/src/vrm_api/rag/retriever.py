"""Cosine top-K retrieval against the embeddings table.

pgvector's `<=>` operator returns cosine distance (0 = identical, 2 = opposite).
We order ascending and convert to similarity = 1 - distance for the response.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Embedding
from .embedder import embed_one


@dataclass
class RetrievedChunk:
    entity_type: str
    entity_id: str
    chunk: str
    similarity: float  # 0..1, higher is better


def retrieve_top_k(
    db: Session,
    query: str,
    *,
    k: int = 8,
    entity_type: str | None = "vendor",
) -> list[RetrievedChunk]:
    """Embed `query`, return the K most similar chunks."""
    if not query.strip():
        return []
    query_vec = embed_one(query)

    stmt = select(
        Embedding.entity_type,
        Embedding.entity_id,
        Embedding.chunk,
        Embedding.vector.cosine_distance(query_vec).label("distance"),
    )
    if entity_type:
        stmt = stmt.where(Embedding.entity_type == entity_type)
    stmt = stmt.order_by("distance").limit(k)

    rows = db.execute(stmt).all()
    return [
        RetrievedChunk(
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            chunk=r.chunk,
            similarity=round(1.0 - float(r.distance), 4),
        )
        for r in rows
    ]
