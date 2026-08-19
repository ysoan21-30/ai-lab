"""Password hashing and JWT token utilities."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Google OAuth helpers
# ---------------------------------------------------------------------------

GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


async def verify_google_token(id_token: str) -> Optional[dict]:
    """Verify a Google ID token and return user info.

    Returns dict with 'email', 'name', 'picture', 'sub' on success, None on failure.
    Uses Google's tokeninfo endpoint for simplicity (no need for google-auth library).
    """
    if not settings.google_oauth_enabled:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(GOOGLE_TOKEN_INFO_URL, params={"id_token": id_token})
            if resp.status_code != 200:
                logger.warning("Google token verification failed: %s", resp.text)
                return None
            data = resp.json()
            # Verify audience matches our client ID
            if data.get("aud") != settings.google_client_id:
                logger.warning("Google token audience mismatch: %s", data.get("aud"))
                return None
            return {
                "email": data["email"],
                "name": data.get("name", ""),
                "picture": data.get("picture", ""),
                "sub": data["sub"],
            }
    except Exception:
        logger.exception("Error verifying Google token")
        return None
