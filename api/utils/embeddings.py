"""
Embedding module — Google text-embedding-004 via google-genai SDK.

Provides a single embed() function used by both the ingest script
and the hybrid retrieval pipeline at query time.
"""

from __future__ import annotations

import os
import time

from google import genai
from google.genai import types as genai_types

EMBEDDING_MODEL = "text-embedding-004"
VECTOR_DIM = 768
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    return _client


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
    client = _get_client()
    for attempt in range(retries):
        try:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=genai_types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=VECTOR_DIM,
                ),
            )
            return result.embeddings[0].values
        except Exception as exc:
            is_rate_limit = "429" in str(exc) or "quota" in str(exc).lower()
            if is_rate_limit and attempt < retries - 1:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Embedding failed after max retries")
