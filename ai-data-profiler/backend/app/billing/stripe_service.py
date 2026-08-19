"""Stripe billing integration.

Structurally implements checkout + webhook handling using real Stripe SDK
calls. Requires STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET / price IDs to be
configured via environment variables before it can process real payments --
see docs/deployment.md for setup. Designed so a Razorpay backend can be
added later behind the same `create_checkout_session` / `handle_webhook`
interface for Indian customers.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import PlanTier, User

logger = logging.getLogger(__name__)

PRICE_ID_BY_TIER = {
    PlanTier.PRO: lambda: settings.stripe_price_id_pro,
    PlanTier.TEAM: lambda: settings.stripe_price_id_team,
}


def _require_stripe():
    if not settings.stripe_secret_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Billing is not configured on this server yet. Set STRIPE_SECRET_KEY, "
                "STRIPE_WEBHOOK_SECRET and the Stripe price IDs in the environment to "
                "enable subscriptions. See docs/deployment.md."
            ),
        )
    import stripe
    stripe.api_key = settings.stripe_secret_key
    return stripe


def create_checkout_session(db: Session, user: User, tier: PlanTier, success_url: str, cancel_url: str) -> str:
    stripe = _require_stripe()
    price_id = PRICE_ID_BY_TIER.get(tier, lambda: None)()
    if not price_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"No Stripe price configured for plan '{tier.value}'.")

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
        user.stripe_customer_id = customer["id"]
        db.commit()

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": str(user.id), "tier": tier.value},
    )
    return session["url"]


def handle_webhook_event(db: Session, payload: bytes, sig_header: str) -> dict:
    stripe = _require_stripe()
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.") from exc

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        tier = data.get("metadata", {}).get("tier")
        if user_id and tier:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.plan = PlanTier(tier)
                user.stripe_subscription_id = data.get("subscription")
                db.commit()

    elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        status_val = data.get("status")
        customer_id = data.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user and status_val in ("canceled", "unpaid", "incomplete_expired"):
            user.plan = PlanTier.FREE
            db.commit()

    return {"status": "processed", "type": event_type}
