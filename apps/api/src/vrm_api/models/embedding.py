"""Embedding row — pgvector-backed vector for the RAG retriever."""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..rag.embedder import EMBEDDING_DIM
from .base import Base, TimestampMixin


class Embedding(Base, TimestampMixin):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # vendor|contract|...
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chunk: Mapped[str] = mapped_column(Text, nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="indexer")

    __table_args__ = (
        # HNSW index for fast cosine-distance search. Optional but cheap to create on 400 rows.
        Index(
            "ix_embeddings_vector_hnsw",
            "vector",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"vector": "vector_cosine_ops"},
        ),
    )
