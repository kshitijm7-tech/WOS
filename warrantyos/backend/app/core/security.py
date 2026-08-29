"""
Password hashing (bcrypt via passlib) and JWT helpers.
Wired up in Phase 1 so Phase 2 (auth) can build directly on it — nothing here issues or
verifies real tokens yet, that lands with the /api/auth routes in Phase 2.
"""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import get_settings

settings = get_settings()

def _init_hasher():
    """
    passlib[bcrypt] is pinned to bcrypt==4.0.1 (see requirements.txt) for compatibility.
    If a newer bcrypt is installed (5.x), passlib's __about__ probe fails loudly; we
    gracefully fall back to direct bcrypt to keep auth working without downgrading at runtime.
    """
    try:
        import bcrypt  # noqa: F401
        # bcrypt 5.x lacks __about__; detect and prefer direct bcrypt in that case
        ver = getattr(bcrypt, "__version__", None)
        if ver and ver.startswith("5."):
            raise ImportError("bcrypt 5.x detected, use direct bcrypt")

        from passlib.context import CryptContext

        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        # warm-up without spamming stderr (passlib logs "(trapped) error..." on failure)
        ctx.hash("probe_warrantyos_123")
        return ctx
    except Exception:
        return None


_pwd_context = _init_hasher()

if _pwd_context is not None:

    def hash_password(plain_password: str) -> str:
        return _pwd_context.hash(plain_password)

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return _pwd_context.verify(plain_password, hashed_password)

else:
    import bcrypt

    def hash_password(plain_password: str) -> str:
        return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
