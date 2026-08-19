"""Webhook configuration CRUD routes (PRO + TEAM)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import PlanTier, User, WebhookConfig
from app.schemas.schemas import WebhookCreate, WebhookOut

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

VALID_EVENTS = {
    "analysis.completed",
    "analysis.failed",
    "alert.triggered",
    "schedule.run_completed",
    "team.member_joined",
    "rule.violation",
}


def _require_pro_or_team(user: User):
    if user.plan == PlanTier.FREE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Webhooks require Pro or Team plan.")


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def create_webhook(
    payload: WebhookCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_pro_or_team(user)

    invalid = set(payload.events) - VALID_EVENTS
    if invalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Invalid events: {invalid}. Valid: {VALID_EVENTS}")

    wh = WebhookConfig(
        user_id=user.id,
        name=payload.name,
        url=payload.url,
        secret=payload.secret,
        events=payload.events,
    )
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return wh


@router.get("", response_model=list[WebhookOut])
def list_webhooks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_pro_or_team(user)
    return (
        db.query(WebhookConfig)
        .filter(WebhookConfig.user_id == user.id)
        .order_by(WebhookConfig.created_at.desc())
        .all()
    )


@router.patch("/{wh_id}/toggle")
def toggle_webhook(
    wh_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wh = db.query(WebhookConfig).filter(
        WebhookConfig.id == wh_id, WebhookConfig.user_id == user.id
    ).first()
    if not wh:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
    wh.is_active = not wh.is_active
    db.commit()
    return {"is_active": wh.is_active}


@router.delete("/{wh_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    wh_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wh = db.query(WebhookConfig).filter(
        WebhookConfig.id == wh_id, WebhookConfig.user_id == user.id
    ).first()
    if not wh:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found.")
    db.delete(wh)
    db.commit()


@router.get("/events")
def list_available_events():
    """Return list of events that can be subscribed to."""
    return {"events": sorted(VALID_EVENTS)}
