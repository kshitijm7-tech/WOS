from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.core.deps import require_role
from app.models.user import User
from app.services.ai_provider_registry import get_provider

router = APIRouter(tags=["system"])



@router.get("/health")
def health():
    """Basic liveness check — no DB dependency, always fast."""
    return {"status": "ok", "service": "WarrantyOS API"}


@router.get("/api/ping-db")
def ping_db(db: Session = Depends(get_db)):
    """Confirms the API can actually reach PostgreSQL — useful for Phase 1 setup checks."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@router.get("/api/admin/ai/health")
def ai_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "support"))
):
    """
    Part 2.6 Admin AI Health & Provider Diagnostics.
    Reports configured provider, active provider, embedding provider, vector store, OCR provider, and fallback status.
    """
    settings = get_settings()
    configured_provider = getattr(settings, "AI_PROVIDER", "mock").lower()
    fallback_enabled = getattr(settings, "AI_FALLBACK_TO_MOCK", True)

    try:
        provider_inst = get_provider()
        active_provider = getattr(provider_inst, "provider_name", "mock").lower()
    except Exception:
        active_provider = "mock"

    fallback_used = (configured_provider != "mock" and active_provider == "mock")
    status = "degraded" if fallback_used else "healthy"

    return {
        "status": status,
        "configured_provider": configured_provider,
        "active_provider": active_provider,
        "embedding_provider": getattr(settings, "AI_EMBEDDING_PROVIDER", "mock"),
        "vector_store": getattr(settings, "AI_VECTOR_STORE", "memory"),
        "ocr_provider": getattr(settings, "AI_OCR_PROVIDER", "mock"),
        "fallback_enabled": bool(fallback_enabled),
        "fallback_used": fallback_used,
        "pipeline_version": getattr(settings, "AI_PIPELINE_VERSION", "2.6"),
    }

