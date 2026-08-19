"""API key generation, hashing, validation for TEAM plan programmatic access."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import ApiKey, PlanTier, User

# Prefix makes keys easily identifiable in logs/configs
API_KEY_PREFIX = "adp_"
API_KEY_BYTES = 32  # 256-bit entropy


def generate_api_key() -> str:
    """Generate a new API key with the adp_ prefix."""
    return API_KEY_PREFIX + secrets.token_hex(API_KEY_BYTES)


def hash_api_key(key: str) -> str:
    """One-way SHA-256 hash of the raw key for safe storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def create_api_key(db: Session, user: User, label: str | None = None) -> tuple[ApiKey, str]:
    """Create a new API key for a user. Returns (db record, raw key).

    The raw key is only available at creation time -- we only store the hash.
    """
    if user.plan != PlanTier.TEAM:
        raise ValueError("API keys are only available on the Team plan.")

    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)

    api_key = ApiKey(
        user_id=user.id,
        key_hash=key_hash,
        label=label,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return api_key, raw_key


def validate_api_key(db: Session, raw_key: str) -> Optional[User]:
    """Look up a raw API key, return the owning User if valid, else None."""
    if not raw_key.startswith(API_KEY_PREFIX):
        return None

    key_hash = hash_api_key(raw_key)
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.revoked == False)  # noqa: E712
        .first()
    )
    if not api_key:
        return None

    # Update last_used timestamp
    api_key.last_used_at = datetime.utcnow()
    db.commit()

    user = db.query(User).filter(User.id == api_key.user_id, User.is_active == True).first()  # noqa: E712
    return user


def list_user_api_keys(db: Session, user: User) -> list[ApiKey]:
    """List all (non-revoked) API keys for a user."""
    return (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user.id, ApiKey.revoked == False)  # noqa: E712
        .order_by(ApiKey.created_at.desc())
        .all()
    )


def revoke_api_key(db: Session, user: User, key_id: str) -> bool:
    """Revoke an API key. Returns True if found and revoked, False otherwise."""
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.user_id == user.id, ApiKey.revoked == False)  # noqa: E712
        .first()
    )
    if not api_key:
        return False

    api_key.revoked = True
    db.commit()
    return True
