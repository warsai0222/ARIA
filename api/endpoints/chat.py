"""
POST /api/chat  — streaming SSE chat endpoint.

Flow:
  1. Validate request
  2. Rate limit check
  3. Prompt injection check
  4. Intent classification (conversational / off_topic / portfolio)
  5. Cache lookup (portfolio queries with no history only)
  6. Hybrid retrieval (portfolio only)
  7. Stream LLM response, yielding SSE events
  8. Log to analytics
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from api.models.schemas import ChatRequest
from api.utils.analytics import log_query, is_deflection
from api.utils.cache import cache
from api.utils.hybrid_retrieval import hybrid_search, build_retrieval_query
from api.utils.intent import classify_intent
from api.utils.llm_pipeline import generate_stream
from api.utils.middleware import check_injection, check_rate_limit, get_client_ip

router = APIRouter()

_OFF_TOPIC_MSG = (
    "I'm ARIA, Varshith's portfolio assistant — I'm only set up to answer questions "
    "about him. Feel free to ask about his projects, skills, background, or how to get in touch!"
)


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    ip = get_client_ip(request)
    check_rate_limit(ip)

    query = body.query.strip()
    history = [m.model_dump() for m in body.history]
    session_id = body.session_id

    # Injection guard — highest priority
    if check_injection(query):
        async def injection_event():
            yield f"data: {json.dumps({'token': _OFF_TOPIC_MSG})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(injection_event(), media_type="text/event-stream")

    # Intent classification — skip RAG for small talk; hard-deflect off-topic
    intent = classify_intent(query)

    if intent == "off_topic":
        async def off_topic_event():
            yield f"data: {json.dumps({'token': _OFF_TOPIC_MSG})}\n\n"
            yield "data: [DONE]\n\n"
        asyncio.create_task(
            log_query(query, session_id, cache_hit=False, couldnt_answer=True,
                      response_snippet=_OFF_TOPIC_MSG, response_time_ms=0)
        )
        return StreamingResponse(off_topic_event(), media_type="text/event-stream")

    start = time.time()

    # Cache: only for portfolio queries with no history (repeat visitors)
    cached = None
    use_cache = (intent == "portfolio") and (len(history) == 0)
    if use_cache:
        cached = cache.get(query)

    if cached:
        async def cached_event():
            yield f"data: {json.dumps({'token': cached})}\n\n"
            yield "data: [DONE]\n\n"

        elapsed = int((time.time() - start) * 1000)
        asyncio.create_task(log_query(query, session_id, cache_hit=True, response_time_ms=elapsed))
        return StreamingResponse(cached_event(), media_type="text/event-stream")

    # Retrieve context — skip entirely for conversational turns
    if intent == "conversational":
        context = ""
    else:
        retrieval_query = build_retrieval_query(query, history)
        try:
            chunks = hybrid_search(retrieval_query, top_k=6)
        except Exception as exc:
            async def error_event():
                yield f"data: {json.dumps({'error': f'Retrieval failed: {exc}'})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(error_event(), media_type="text/event-stream")
        context = "\n\n---\n\n".join(chunks) if chunks else ""

    # Stream LLM response
    full_response: list[str] = []

    async def event_stream():
        nonlocal full_response
        try:
            async for token in generate_stream(query, context, history):
                full_response.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
            # Post-stream: cache if no history, log analytics
            elapsed = int((time.time() - start) * 1000)
            complete = "".join(full_response)
            couldnt = is_deflection(complete)
            if use_cache and complete and not couldnt:
                cache.set(query, complete)
            asyncio.create_task(
                log_query(
                    query,
                    session_id,
                    cache_hit=False,
                    couldnt_answer=couldnt,
                    response_snippet=complete[:500],
                    response_time_ms=elapsed,
                )
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
