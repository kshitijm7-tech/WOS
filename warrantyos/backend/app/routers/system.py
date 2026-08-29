from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

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
