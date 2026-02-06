from fastapi import APIRouter

from src.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health_check():
    settings = get_settings()
    return {"status": "healthy", "stage": settings.stage}
