"""
Qdrant Cloud store — ARIA-specific wrapper.

Provides a lazy singleton client and a search function used by hybrid retrieval.
"""

from __future__ import annotations

import os
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

COLLECTION = "aria_chunks"
_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    """Lazy singleton Qdrant Cloud client."""
    global _client
    if _client is None:
        _client = QdrantClient(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ["QDRANT_API_KEY"],
        )
    return _client


def scroll_all_chunks() -> list[dict[str, Any]]:
    """
    Scroll all chunks from the collection — used to build the BM25 index at startup.
    Returns a flat list of dicts with {id, text, section, name, chunk_index}.
    """
    client = get_client()
    records: list[dict[str, Any]] = []
    offset = None

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            records.append({
                "id": point.id,
                "text": text,
                "section": payload.get("section", ""),
                "name": payload.get("name", ""),
                "chunk_index": payload.get("chunk_index", 0),
            })
        if offset is None:
            break

    return records


def dense_search(query_vector: list[float], top_k: int = 6) -> list[dict[str, Any]]:
    """
    Dense cosine similarity search over aria_chunks.
    Returns list of {id, score, text, section, name}.
    """
    client = get_client()
    results = client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    ).points
    return [
        {
            "id": r.id,
            "score": r.score,
            "text": (r.payload or {}).get("text", ""),
            "section": (r.payload or {}).get("section", ""),
            "name": (r.payload or {}).get("name", ""),
        }
        for r in results
    ]
