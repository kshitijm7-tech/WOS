"""
WarrantyOS API entrypoint.

Run with:
    uvicorn app.main:app --reload --port 8000
(from inside /backend, with the venv active — see /README.md)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import Base, engine
from app import models  # noqa: F401  (import registers all tables on Base.metadata)
from app.routers import auth, system, claims, admin_claims, products, ai, reviews, evaluation

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hackathon-simple table creation. Safe to call repeatedly — only creates what's missing.
    Base.metadata.create_all(bind=engine)
    # Ensure upload directory exists for future file-upload feature (Phase 3)
    # Validates infrastructure early; no files are written yet.
    try:
        from pathlib import Path

        Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    yield


app = FastAPI(
    title="WarrantyOS API",
    description="AI-assisted warranty & returns arbiter — hybrid rules + AI + human review.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(admin_claims.router)
app.include_router(products.router)
app.include_router(ai.router)
app.include_router(reviews.router)
app.include_router(evaluation.router)
