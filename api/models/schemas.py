from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text")


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="User's question")
    history: list[ChatMessage] = Field(default_factory=list, description="Previous turns")
    session_id: str = Field(default="", description="Optional session identifier for analytics")


class HealthResponse(BaseModel):
    status: str
    model: str
    collection: str


class SuggestedResponse(BaseModel):
    questions: list[str]
