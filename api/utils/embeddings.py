"""
Embedding module — sentence-transformers (local, no API key required).

Uses all-MiniLM-L6-v2: 80MB, 384-dim, fast, no external dependencies.
Model is cached after first download.
"""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
VECTOR_DIM = 384
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed(text: str, task_type: str = "retrieval_query", retries: int = 3) -> list[float]:
    """
    Embed text using a local sentence-transformers model.

    Args:
        text: The text to embed.
        task_type: Ignored (kept for API compatibility).
        retries: Ignored (local model doesn't fail on rate limits).

    Returns:
        384-dimensional embedding vector.
    """
    model = _get_model()
    return model.encode(text, normalize_embeddings=True).tolist()
