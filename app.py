"""
ARIA — AI Retrieval & Intelligence Assistant
Varshith Tipirneni's portfolio chatbot backend.

Run locally:
    uvicorn app:app --reload --port 8000

Environment variables: see .env.example
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

# Add project root to path (needed for Vercel / HF Spaces)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.endpoints import chat, health, suggested
from api.utils.hybrid_retrieval import warm_up
from api.utils.middleware import SecurityMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-build the BM25 index at startup so the first request is fast."""
    try:
        warm_up()
        print("✓ ARIA — BM25 index ready")
    except Exception as exc:
        print(f"⚠ ARIA — warm-up failed (is Qdrant configured?): {exc}")
    yield


app = FastAPI(
    title="ARIA",
    description="Varshith Tipirneni's portfolio AI assistant",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# CORS — allow all origins so the widget can be embedded anywhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=False,
)
app.add_middleware(SecurityMiddleware)

app.include_router(health.router, prefix="/api")
app.include_router(suggested.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/")
async def root():
    return RedirectResponse(url="/chat")
