from fastapi import APIRouter
from api.models.schemas import HealthResponse
from api.utils.llm_pipeline import GROQ_MODEL
from api.utils.qdrant_store import COLLECTION

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=GROQ_MODEL,
        collection=COLLECTION,
    )
