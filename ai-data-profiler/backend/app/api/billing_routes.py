"""Billing endpoints: plan info, Stripe checkout, webhook."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.billing.plans import PLAN_DEFAULTS
from app.billing.stripe_service import create_checkout_session, handle_webhook_event
from app.core.config import settings
from app.db.session import get_db
from app.models.models import PlanTier, User

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans")
def list_plans():
    return {tier.value: config for tier, config in PLAN_DEFAULTS.items()}


@router.post("/checkout/{tier}")
def checkout(tier: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan_tier = PlanTier(tier)
    url = create_checkout_session(
        db, user, plan_tier,
        success_url=f"{settings.frontend_url}/dashboard?checkout=success",
        cancel_url=f"{settings.frontend_url}/pricing?checkout=cancelled",
    )
    return {"checkout_url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    return handle_webhook_event(db, payload, sig_header)
