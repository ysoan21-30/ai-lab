"""Shareable report routes — create public links, view shared reports."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import hash_password, verify_password
from app.core.config import settings
from app.db.session import get_db
from app.models.models import Analysis, PlanTier, ShareableReport, User
from app.schemas.schemas import AnalysisDetail, ShareableReportOut, ShareReportCreate
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/share", response_model=ShareableReportOut, status_code=status.HTTP_201_CREATED)
def create_shared_report(
    payload: ShareReportCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.plan == PlanTier.FREE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Shareable reports require Pro or Team plan.")

    analysis = db.query(Analysis).filter(
        Analysis.id == payload.analysis_id, Analysis.user_id == user.id
    ).first()
    if not analysis:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found.")

    token = secrets.token_urlsafe(32)
    expires_at = None
    if payload.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=payload.expires_in_days)

    report = ShareableReport(
        analysis_id=analysis.id,
        user_id=user.id,
        share_token=token,
        title=payload.title or analysis.dataset_name,
        is_public=payload.is_public,
        password_hash=hash_password(payload.password) if payload.password else None,
        expires_at=expires_at,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    log_action(db, user_id=user.id, action="share",
               resource_type="analysis", resource_id=analysis.id)

    out = ShareableReportOut.model_validate(report)
    out.has_password = bool(report.password_hash)
    out.share_url = f"{settings.frontend_url}/shared/{token}"
    return out


@router.get("/shared", response_model=list[ShareableReportOut])
def list_shared_reports(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = (
        db.query(ShareableReport)
        .filter(ShareableReport.user_id == user.id)
        .order_by(ShareableReport.created_at.desc())
        .all()
    )
    results = []
    for r in reports:
        out = ShareableReportOut.model_validate(r)
        out.has_password = bool(r.password_hash)
        out.share_url = f"{settings.frontend_url}/shared/{r.share_token}"
        results.append(out)
    return results


@router.get("/shared/{token}", response_model=AnalysisDetail)
def view_shared_report(
    token: str,
    password: str | None = None,
    db: Session = Depends(get_db),
):
    """Public endpoint — no auth required. Returns the analysis data for a shared report."""
    report = db.query(ShareableReport).filter(
        ShareableReport.share_token == token,
        ShareableReport.is_public == True,
    ).first()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found or not public.")

    # Check expiry
    if report.expires_at and report.expires_at < datetime.utcnow():
        raise HTTPException(status.HTTP_410_GONE, "This shared report has expired.")

    # Check password
    if report.password_hash:
        if not password or not verify_password(password, report.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password required or incorrect.")

    # Increment view count
    report.view_count = (report.view_count or 0) + 1
    db.commit()

    analysis = db.query(Analysis).filter(Analysis.id == report.analysis_id).first()
    if not analysis:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis data not found.")

    return analysis


@router.delete("/share/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_shared_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(ShareableReport).filter(
        ShareableReport.id == report_id, ShareableReport.user_id == user.id
    ).first()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    db.delete(report)
    db.commit()
