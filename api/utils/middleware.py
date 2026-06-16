"""
Security middleware:
  - IP-based rate limiting (20 req/hour per IP)
  - Origin check (configurable allowed origins)
  - Prompt injection patterns checked at the endpoint level (see chat.py)
"""

from __future__ import annotations

import os
import time
from collections import defaultdict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Prompt injection patterns — ported from HybridRAG security.py
INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "disregard your instructions",
    "forget your instructions",
    "override your instructions",
    "you are now",
    "act as",
    "pretend you are",
    "pretend to be",
    "your new instructions",
    "reveal your system prompt",
    "show me your prompt",
    "what are your instructions",
    "print your system prompt",
]

# Rate limit state — per IP
_rate_limit: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 20       # requests
RATE_WINDOW = 3600    # seconds (1 hour)


def get_allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    # Always allow localhost for local dev
    return origins + ["http://localhost:3000", "http://localhost:5500", "http://127.0.0.1:5500"]


def check_rate_limit(ip: str) -> None:
    """Raise HTTPException 429 if IP exceeds the rate limit."""
    now = time.time()
    window_start = now - RATE_WINDOW
    # Keep only requests within the window
    _rate_limit[ip] = [t for t in _rate_limit[ip] if t > window_start]
    if len(_rate_limit[ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in an hour.")
    _rate_limit[ip].append(now)


def check_injection(text: str) -> bool:
    """Return True if the text contains a known injection pattern."""
    lower = text.lower()
    return any(pattern in lower for pattern in INJECTION_PATTERNS)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Lightweight middleware that checks Origin on non-health endpoints.
    Rate limiting is handled per-endpoint to avoid buffering the request body.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip checks for health endpoint
        if request.url.path in ("/api/health", "/"):
            return await call_next(request)

        # Origin check
        origin = request.headers.get("origin") or request.headers.get("referer", "")
        allowed = get_allowed_origins()
        # Allow requests with no origin header (e.g. server-to-server, curl during dev)
        # Only block when origin is explicitly set and NOT in the allow list
        if origin and not any(o in origin for o in allowed):
            return Response(
                content='{"detail":"Origin not allowed"}',
                status_code=403,
                media_type="application/json",
            )

        return await call_next(request)
