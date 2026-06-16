"""
Embedding module — Google text-embedding-004.

Provides a single embed() function used by both the ingest script
and the hybrid retrieval pipeline at query time.
"""

from __future__ import annotations

import os
import time

import google.generativeai as genai

EMBEDDING_MODEL = "models/text-embedding-004"
VECTOR_DIM = 768
_configured = False


def _ensure_configured() -> None:
    global _configured
    if not _configured:
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        _configured = True


def embed(text: str, task_type: str = "retrieval_query", retries: int = 3) -> list[float]:
    """
    Embed text using Google text-embedding-004.

    Args:
        text: The text to embed.
        task_type: "retrieval_query" for queries, "retrieval_document" for indexing.
        retries: Number of retry attempts on rate limit.

    Returns:
        768-dimensional embedding vector.
    """
    _ensure_configured()
    for attempt in range(retries):
        try:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text,
                task_type=task_type,
                output_dimensionality=VECTOR_DIM,
            )
            return result["embedding"]
        except Exception as exc:
            is_rate_limit = "429" in str(exc) or "quota" in str(exc).lower()
            if is_rate_limit and attempt < retries - 1:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Embedding failed after max retries")
