"""API key management endpoints for TEAM plan users."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.api_keys import create_api_key, list_user_api_keys, revoke_api_key
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import PlanTier, User

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


class CreateKeyRequest(BaseModel):
    label: str | None = None


class ApiKeyOut(BaseModel):
    id: str
    label: str | None
    created_at: str
    last_used_at: str | None

    class Config:
        from_attributes = True


class ApiKeyCreatedOut(ApiKeyOut):
    """Returned only at creation time -- includes the raw key."""
    raw_key: str


def _require_team(user: User) -> None:
    if user.plan != PlanTier.TEAM:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="API keys are only available on the Team plan. Please upgrade.",
        )


@router.post("", response_model=ApiKeyCreatedOut, status_code=status.HTTP_201_CREATED)
def create_key(
    payload: CreateKeyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_team(user)
    api_key, raw_key = create_api_key(db, user, label=payload.label)
    return ApiKeyCreatedOut(
        id=api_key.id,
        label=api_key.label,
        created_at=str(api_key.created_at),
        last_used_at=str(api_key.last_used_at) if api_key.last_used_at else None,
        raw_key=raw_key,
    )


@router.get("", response_model=list[ApiKeyOut])
def list_keys(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_team(user)
    keys = list_user_api_keys(db, user)
    return [
        ApiKeyOut(
            id=k.id,
            label=k.label,
            created_at=str(k.created_at),
            last_used_at=str(k.last_used_at) if k.last_used_at else None,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_team(user)
    if not revoke_api_key(db, user, key_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found.")
