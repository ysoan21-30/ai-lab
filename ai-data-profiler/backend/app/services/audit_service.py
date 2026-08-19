"""Audit trail service — logs user actions for compliance and debugging."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.models import AuditAction, AuditLog

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    user_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    team_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Record an action in the audit log."""
    try:
        audit_action = AuditAction(action)
    except ValueError:
        # Store as-is if not a known enum value — we log the string in details
        audit_action = AuditAction.UPDATE
        details = details or {}
        details["raw_action"] = action

    entry = AuditLog(
        user_id=user_id,
        team_id=team_id,
        action=audit_action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to write audit log")


def get_audit_logs(
    db: Session,
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Query audit logs with optional filters."""
    query = db.query(AuditLog)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if team_id:
        query = query.filter(AuditLog.team_id == team_id)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    return (
        query.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
