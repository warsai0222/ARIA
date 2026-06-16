from fastapi import APIRouter
from api.models.schemas import SuggestedResponse

router = APIRouter()

SUGGESTED_QUESTIONS = [
    "What AI projects has Varshith built?",
    "What makes him a strong AI engineering candidate?",
    "Tell me about his RAG experience",
    "What's his tech stack?",
    "Is he open to new opportunities?",
]


@router.get("/suggested", response_model=SuggestedResponse)
async def suggested() -> SuggestedResponse:
    return SuggestedResponse(questions=SUGGESTED_QUESTIONS)
