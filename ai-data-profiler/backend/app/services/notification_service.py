"""Notification service — email, Slack, webhook delivery."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import WebhookConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Email via SMTP
# ---------------------------------------------------------------------------

def send_email(
    to: str,
    subject: str,
    html_body: str,
    plain_body: Optional[str] = None,
) -> bool:
    """Send an email via SMTP. Returns True on success."""
    if not settings.smtp_enabled:
        logger.info("SMTP not configured — skipping email to %s", to)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to

    if plain_body:
        msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


# ---------------------------------------------------------------------------
# Slack webhook
# ---------------------------------------------------------------------------

def send_slack_message(
    text: str,
    webhook_url: Optional[str] = None,
    blocks: Optional[list] = None,
) -> bool:
    """Post a message to a Slack webhook."""
    url = webhook_url or settings.slack_webhook_url
    if not url:
        logger.info("No Slack webhook configured — skipping")
        return False

    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Slack message sent")
                return True
            logger.warning("Slack webhook returned %s: %s", resp.status_code, resp.text)
            return False
    except Exception:
        logger.exception("Failed to send Slack message")
        return False


# ---------------------------------------------------------------------------
# Webhook delivery
# ---------------------------------------------------------------------------

def deliver_webhook(
    config: WebhookConfig,
    event: str,
    payload: dict,
    db: Optional[Session] = None,
) -> bool:
    """Deliver a webhook payload to the configured URL."""
    body = json.dumps({"event": event, "timestamp": datetime.utcnow().isoformat(), "data": payload})

    headers = {"Content-Type": "application/json"}
    if config.secret:
        signature = hmac.new(config.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = signature

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(config.url, content=body, headers=headers)
            success = 200 <= resp.status_code < 300

        if db:
            config.last_triggered_at = datetime.utcnow()
            if not success:
                config.failure_count = (config.failure_count or 0) + 1
            else:
                config.failure_count = 0
            db.commit()

        return success
    except Exception:
        logger.exception("Webhook delivery failed for %s", config.url)
        if db:
            config.failure_count = (config.failure_count or 0) + 1
            db.commit()
        return False


def fire_webhooks(
    db: Session,
    user_id: str,
    event: str,
    payload: dict,
    team_id: Optional[str] = None,
):
    """Fire all active webhooks for a user/team that subscribe to the given event."""
    query = db.query(WebhookConfig).filter(
        WebhookConfig.user_id == user_id,
        WebhookConfig.is_active == True,
    )
    if team_id:
        query = query.filter(
            (WebhookConfig.team_id == team_id) | (WebhookConfig.team_id == None)
        )

    for wh in query.all():
        if event in (wh.events or []):
            deliver_webhook(wh, event, payload, db)


# ---------------------------------------------------------------------------
# Alert dispatcher — used by scheduled analysis
# ---------------------------------------------------------------------------

def send_alert(
    channels: list[str],
    subject: str,
    message: str,
    user_email: Optional[str] = None,
    slack_url: Optional[str] = None,
):
    """Dispatch an alert to configured channels."""
    if "email" in channels and user_email:
        send_email(
            to=user_email,
            subject=f"[AI Data Profiler] {subject}",
            html_body=f"<h3>{subject}</h3><p>{message}</p>",
            plain_body=f"{subject}\n\n{message}",
        )
    if "slack" in channels:
        send_slack_message(f"*{subject}*\n{message}", webhook_url=slack_url)
