"""Embedding provider — fastembed with BAAI/bge-small-en-v1.5 (384-dim, ONNX).

Why fastembed and not the LLM provider's embeddings?
  * The user's Ollama daemon doesn't have embeddings enabled.
  * Anthropic doesn't ship an embeddings API.
  * fastembed gives us a single deterministic path that works regardless of
    which LLM provider is configured — and downloads its model on first use
    so there's no Ollama pull required.

Model: BAAI/bge-small-en-v1.5 — 384-dim, ~133 MB on disk, fast on CPU, MTEB-strong.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_logger

if TYPE_CHECKING:
    from fastembed import TextEmbedding

log = get_logger(__name__)

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

_embedder: "TextEmbedding | None" = None


def get_embedder() -> "TextEmbedding":
    """Singleton — first call downloads the ~133 MB ONNX model and caches it."""
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding  # local import — heavy at module load

        log.info("loading_embedder", model=EMBEDDING_MODEL)
        _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
        log.info("embedder_ready", model=EMBEDDING_MODEL, dim=EMBEDDING_DIM)
    return _embedder


def embed_one(text: str) -> list[float]:
    return embed_many([text])[0]


def embed_many(texts: list[str]) -> list[list[float]]:
    """Batch-embed. Returns one 384-dim vector per input."""
    if not texts:
        return []
    embedder = get_embedder()
    # fastembed returns a generator of np.ndarray
    return [vec.tolist() for vec in embedder.embed(texts)]
