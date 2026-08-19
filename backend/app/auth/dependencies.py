"""FastAPI auth dependencies: current user (JWT or API key), admin-only guard."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.api_keys import validate_api_key
from app.auth.security import decode_token
from app.db.session import get_db
from app.models.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    # 1. Try JWT Bearer token first
    if credentials:
        payload = decode_token(credentials.credentials)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.is_active:
                return user

    # 2. Try API key via X-API-Key header
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        user = validate_api_key(db, api_key_header)
        if user:
            return user
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key")

    # 3. Neither worked
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
