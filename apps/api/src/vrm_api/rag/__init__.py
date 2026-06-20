"""RAG pipeline.

Submodules import directly to avoid circular imports with vrm_api.models:
    from vrm_api.rag.embedder import get_embedder, EMBEDDING_DIM
    from vrm_api.rag.indexer import reindex_all, build_vendor_chunk
    from vrm_api.rag.retriever import retrieve_top_k, RetrievedChunk
    from vrm_api.rag.prompts import ASK_SYSTEM_PROMPT, build_user_prompt
"""
