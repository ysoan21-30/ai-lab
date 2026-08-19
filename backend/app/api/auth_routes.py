"""Authentication endpoints: register, login, refresh, me, Google OAuth."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import (
    create_access_token, create_refresh_token, decode_token,
    hash_password, verify_google_token, verify_password,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.models import PlanTier, User
from app.schemas.schemas import GoogleOAuthRequest, TokenResponse, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        plan=PlanTier.FREE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token.")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/google", response_model=TokenResponse)
async def google_oauth(payload: GoogleOAuthRequest, db: Session = Depends(get_db)):
    """Sign in or register via Google OAuth."""
    if not settings.google_oauth_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Google OAuth is not configured.")

    google_user = await verify_google_token(payload.credential)
    if not google_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential.")

    email = google_user["email"].lower()
    user = db.query(User).filter(User.email == email).first()

    if user:
        # Existing user — update profile if needed
        if not user.avatar_url and google_user.get("picture"):
            user.avatar_url = google_user["picture"]
        if user.auth_provider == "local":
            user.auth_provider = "google"  # link Google to existing account
    else:
        # New user via Google
        user = User(
            email=email,
            hashed_password=None,
            full_name=google_user.get("name"),
            avatar_url=google_user.get("picture"),
            auth_provider="google",
            plan=PlanTier.FREE,
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.get("/google/config")
def google_config():
    """Return Google OAuth client ID for frontend (public endpoint)."""
    return {
        "enabled": settings.google_oauth_enabled,
        "client_id": settings.google_client_id if settings.google_oauth_enabled else None,
    }
