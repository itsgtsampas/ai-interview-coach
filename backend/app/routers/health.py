from fastapi import APIRouter

from app.config import get_settings
from app.llm.provider import get_llm_provider

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def ready() -> dict:
    settings = get_settings()
    checks = {"database": False, "vector_store": False, "llm_provider": False}
    try:
        from sqlmodel import Session, text

        from app.db import engine

        with Session(engine) as s:
            s.exec(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    try:
        from app.rag.store import get_collection

        get_collection().count()
        checks["vector_store"] = True
    except Exception:
        pass
    try:
        checks["llm_provider"] = bool(get_llm_provider().name)
    except Exception:
        pass
    return {
        "status": "ok" if all(checks.values()) else "degraded",
        "checks": checks,
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
    }
