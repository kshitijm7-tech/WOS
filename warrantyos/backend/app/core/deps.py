"""
FastAPI dependencies for authentication/authorization. Any route that needs a logged-in
user depends on get_current_user; any route restricted to specific roles depends on
require_role(...) instead.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# tokenUrl is only used by interactive docs to know where to get a token from — the actual
# verification below doesn't call it.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials. Please log in again.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise CREDENTIALS_ERROR
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        if not email:
            raise CREDENTIALS_ERROR
    except JWTError:
        raise CREDENTIALS_ERROR

    user = db.query(User).options(joinedload(User.role)).filter(User.email == email).first()
    if not user or not user.is_active:
        raise CREDENTIALS_ERROR
    # role must be present for authorization checks
    if not user.role:
        raise CREDENTIALS_ERROR
    return user


def require_role(*roles: str):
    """Usage: Depends(require_role("admin")) or Depends(require_role("admin", "support"))"""

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to do that.",
            )
        return current_user

    return checker
