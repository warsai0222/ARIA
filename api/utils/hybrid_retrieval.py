"""
Hybrid retrieval — BM25 + dense + RRF fusion.

Ported from PRISM src/retrieval/hybrid.py and adapted for:
  - Qdrant Cloud (not local path)
  - Google text-embedding-004 (not sentence-transformers)
  - ARIA's flat chunk schema (no document_id filtering needed)
  - Module-level singleton BM25 index (built once at first request)

The BM25 index is built by scrolling all ~30 chunks from Qdrant Cloud
and kept in memory for the lifetime of the process. On HF Spaces this
means one build per cold start — acceptable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rank_bm25 import BM25Okapi

from api.utils.embeddings import embed
from api.utils.qdrant_store import dense_search, scroll_all_chunks

RRF_K = 60
_bm25_index: "_BM25Index | None" = None


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class _BM25Index:
    records: list[dict[str, Any]]
    corpus: list[list[str]]
    index: BM25Okapi


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_bm25() -> _BM25Index:
    records = scroll_all_chunks()
    if not records:
        raise RuntimeError("No chunks found in Qdrant — run scripts/ingest.py first.")
    corpus = [_tokenize(r["text"]) for r in records]
    return _BM25Index(records=records, corpus=corpus, index=BM25Okapi(corpus))


def _get_bm25() -> _BM25Index:
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = _build_bm25()
    return _bm25_index


def _bm25_search(query: str, top_k: int) -> list[dict[str, Any]]:
    idx = _get_bm25()
    tokens = _tokenize(query)
    if not tokens:
        return []
    scores = idx.index.get_scores(tokens)
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    results = []
    for pos in ranked:
        if float(scores[pos]) <= 0:
            break
        rec = dict(idx.records[pos])
        rec["score"] = float(scores[pos])
        results.append(rec)
        if len(results) >= top_k:
            break
    return results


# ---------------------------------------------------------------------------
# RRF fusion (same logic as PRISM)
# ---------------------------------------------------------------------------

def _fuse(bm25_results: list[dict], dense_results: list[dict]) -> list[dict]:
    fused: dict[str, dict] = {}

    for rank, result in enumerate(bm25_results, start=1):
        rid = str(result["id"])
        entry = fused.setdefault(rid, {**result, "rrf_score": 0.0})
        entry["rrf_score"] += 1.0 / (RRF_K + rank)
        entry["bm25_rank"] = rank
        entry["bm25_score"] = result.get("score")

    for rank, result in enumerate(dense_results, start=1):
        rid = str(result["id"])
        entry = fused.setdefault(rid, {**result, "rrf_score": 0.0})
        entry["rrf_score"] += 1.0 / (RRF_K + rank)
        entry["dense_rank"] = rank
        entry["dense_score"] = result.get("score")

    return sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def hybrid_search(query: str, top_k: int = 6) -> list[str]:
    """
    Run BM25 + dense retrieval and fuse with RRF.

    Returns the top_k chunk texts, ready to join as context for the LLM.
    """
    fetch_k = top_k * 2  # fetch more candidates so RRF has a richer pool

    query_vec = embed(query, task_type="retrieval_query")
    bm25_results = _bm25_search(query, top_k=fetch_k)
    dense_results = dense_search(query_vec, top_k=fetch_k)

    fused = _fuse(bm25_results, dense_results)
    return [r["text"] for r in fused[:top_k] if r.get("text")]


def build_retrieval_query(query: str, history: list[dict]) -> str:
    """
    Prepend recent user messages to the query for context-aware retrieval.
    Improves follow-up questions like "tell me more" or "what about that project?"
    by anchoring retrieval to the conversation thread.
    """
    recent_user = [
        m.get("content", "")
        for m in history[-4:]
        if m.get("role", "").lower() == "user"
    ]
    if recent_user:
        return " | ".join(recent_user) + " | " + query
    return query


def warm_up() -> None:
    """
    Pre-build the BM25 index on startup so the first request isn't slow.
    Call this from the FastAPI lifespan event.
    """
    _get_bm25()
