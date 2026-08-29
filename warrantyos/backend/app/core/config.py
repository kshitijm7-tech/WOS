"""
Central app configuration, read from environment variables (see /.env.example).
Never hardcode secrets — everything here has a safe hackathon-mode default.
"""

import os
import warnings
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env location deterministically: warrantyos/.env -> backend/.env -> cwd/.env
# This supports both Docker (warrantyos/.env) and local `uvicorn` from /backend.
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
for _p in [_ROOT_ENV, _BACKEND_ENV]:
    if _p.exists():
        load_dotenv(dotenv_path=_p, override=False)
        break
else:
    # fallback to cwd lookup for any other invocation style
    load_dotenv(override=False)


class Settings:
    APP_NAME: str = "WarrantyOS"
    ENV: str = os.getenv("ENV", "development")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://warrantyos:warrantyos@localhost:5432/warrantyos",
    )

    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-only-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    # "mock" (default, no key needed) or "rocketride" once the real SDK is connected
    ROCKETRIDE_MODE: str = os.getenv("ROCKETRIDE_MODE", "mock")
    ROCKETRIDE_API_KEY: str = os.getenv("ROCKETRIDE_API_KEY", "")

    # Part 2.4: AI Execution (provider-agnostic, offline mock only)
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "mock")
    AI_MODEL: str = os.getenv("AI_MODEL", "mock-v1")
    AI_PIPELINE_VERSION: str = os.getenv("AI_PIPELINE_VERSION", "2.4")
    AI_EXECUTION_TIMEOUT_SECONDS: int = int(os.getenv("AI_EXECUTION_TIMEOUT_SECONDS", "30"))
    AI_MAX_ATTEMPTS: int = int(os.getenv("AI_MAX_ATTEMPTS", "2"))

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "20"))

    CORS_ORIGINS: list = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

    def __init__(self) -> None:
        # Resolve SQLite relative paths to absolute (backend/ vs repo root ambiguity)
        if self.DATABASE_URL.startswith("sqlite"):
            # Handle sqlite:///./warrantyos.db, sqlite:///warrantyos.db, sqlite:////absolute
            if self.DATABASE_URL.startswith("sqlite:///./"):
                rel = self.DATABASE_URL.replace("sqlite:///./", "")
                backend_dir = Path(__file__).resolve().parents[2]
                self.DATABASE_URL = f"sqlite:///{(backend_dir / rel).resolve().as_posix()}"
            elif self.DATABASE_URL.startswith("sqlite:///") and not self.DATABASE_URL.startswith("sqlite:////"):
                # sqlite:///relative/path.db -> resolve if not absolute
                raw_path = self.DATABASE_URL.replace("sqlite:///", "", 1)
                p = Path(raw_path)
                if not p.is_absolute():
                    backend_dir = Path(__file__).resolve().parents[2]
                    self.DATABASE_URL = f"sqlite:///{(backend_dir / p).resolve().as_posix()}"
        # Security: warn if default JWT secret is used in non-dev env
        if self.ENV != "development" and self.JWT_SECRET == "dev-only-secret-change-me":
            warnings.warn("JWT_SECRET is using insecure default — set a strong secret in .env", UserWarning)
        if self.ENV != "development" and len(self.JWT_SECRET) < 32:
            warnings.warn("JWT_SECRET should be at least 32 characters in production", UserWarning)


@lru_cache
def get_settings() -> Settings:
    return Settings()
