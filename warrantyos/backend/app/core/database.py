"""
SQLAlchemy engine/session setup. Tables are created via Base.metadata.create_all() on
startup for hackathon simplicity (see main.py). From Phase 2 onward, feel free to replace
this with Alembic migrations for anything beyond the demo.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import get_settings

settings = get_settings()

# SQLite needs check_same_thread=False for FastAPI's threaded usage; pooling
# differs between SQLite (SingleThread) and PostgreSQL (QueuePool with pre-ping).
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # Use StaticPool for in-memory or NullPool-like behavior; default QueuePool is fine for file-based SQLite
    engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=False)
else:
    connect_args = {}
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session per request, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
