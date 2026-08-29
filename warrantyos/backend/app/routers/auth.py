from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import Admin, Customer, Role, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    # user.role is eagerly loaded in login/register/me; fallback to safe accessor
    role_name = user.role.name if user.role else "customer"
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, role=role_name)


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Public customer self-signup. Admin accounts are provisioned separately (seed.py for
    the demo) — there is no public admin registration endpoint."""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    customer_role = db.query(Role).filter(Role.name == "customer").first()
    if not customer_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Roles are not seeded yet. Run `python seed.py` in /backend first.",
        )

    user = User(
        email=payload.email.lower().strip(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role_id=customer_role.id,
    )
    try:
        db.add(user)
        db.flush()  # assigns user.id without committing
        db.add(Customer(user_id=user.id))
        db.commit()
        db.refresh(user)
        # ensure role relationship is available for _user_out
        user = db.query(User).options(joinedload(User.role)).filter(User.id == user.id).first()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    token = create_access_token(subject=user.email, role=customer_role.name)
    return TokenResponse(access_token=token, user=_user_out(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    # email lookup is case-insensitive; stored emails are normalized to lower
    email = payload.email.lower().strip()
    user = db.query(User).options(joinedload(User.role)).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled. Contact support.",
        )

    token = create_access_token(subject=user.email, role=user.role.name)
    return TokenResponse(access_token=token, user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return _user_out(current_user)
