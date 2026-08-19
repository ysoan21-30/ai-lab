"""Audit trail query routes (TEAM plan or admin)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import PlanTier, User
from app.schemas.schemas import AuditLogOut
from app.services.audit_service import get_audit_logs

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    resource_type: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List audit logs for the current user (or team if TEAM plan)."""
    if user.plan == PlanTier.FREE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Audit trail requires Pro or Team plan.")

    logs = get_audit_logs(
        db,
        user_id=user.id if not user.is_admin else None,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )

    results = []
    for log in logs:
        out = AuditLogOut.model_validate(log)
        if log.user:
            out.user_email = log.user.email
        results.append(out)
    return results
