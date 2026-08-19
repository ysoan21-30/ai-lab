"""Scheduled analysis CRUD + run history routes (PRO + TEAM)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import (
    AlertSeverity, PlanTier, ScheduleFrequency, ScheduleRun,
    ScheduledAnalysis, User,
)
from app.schemas.schemas import ScheduledAnalysisCreate, ScheduledAnalysisOut, ScheduleRunOut
from app.services.scheduler_service import create_schedule, execute_scheduled_run

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _require_pro_or_team(user: User):
    if user.plan == PlanTier.FREE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Scheduled analysis requires Pro or Team plan.")


@router.post("", response_model=ScheduledAnalysisOut, status_code=status.HTTP_201_CREATED)
def create(
    payload: ScheduledAnalysisCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_pro_or_team(user)
    try:
        freq = ScheduleFrequency(payload.frequency)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid frequency: {payload.frequency}")

    try:
        severity = AlertSeverity(payload.alert_severity)
    except ValueError:
        severity = AlertSeverity.WARNING

    schedule = ScheduledAnalysis(
        user_id=user.id,
        name=payload.name,
        source_type=payload.source_type,
        connection_id=payload.connection_id,
        query=payload.query,
        frequency=freq,
        cron_expression=payload.cron_expression,
        alert_on_quality_drop=payload.alert_on_quality_drop,
        alert_on_row_count_change=payload.alert_on_row_count_change,
        alert_severity=severity,
        alert_channels=payload.alert_channels,
    )
    return create_schedule(db, schedule)


@router.get("", response_model=list[ScheduledAnalysisOut])
def list_schedules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_pro_or_team(user)
    return (
        db.query(ScheduledAnalysis)
        .filter(ScheduledAnalysis.user_id == user.id)
        .order_by(ScheduledAnalysis.created_at.desc())
        .all()
    )


@router.get("/{schedule_id}", response_model=ScheduledAnalysisOut)
def get_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schedule = db.query(ScheduledAnalysis).filter(
        ScheduledAnalysis.id == schedule_id,
        ScheduledAnalysis.user_id == user.id,
    ).first()
    if not schedule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schedule not found.")
    return schedule


@router.post("/{schedule_id}/run", response_model=ScheduleRunOut)
def trigger_run(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a scheduled analysis run."""
    _require_pro_or_team(user)
    schedule = db.query(ScheduledAnalysis).filter(
        ScheduledAnalysis.id == schedule_id,
        ScheduledAnalysis.user_id == user.id,
    ).first()
    if not schedule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schedule not found.")
    run = execute_scheduled_run(db, schedule)
    return run


@router.get("/{schedule_id}/runs", response_model=list[ScheduleRunOut])
def list_runs(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schedule = db.query(ScheduledAnalysis).filter(
        ScheduledAnalysis.id == schedule_id,
        ScheduledAnalysis.user_id == user.id,
    ).first()
    if not schedule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schedule not found.")
    return (
        db.query(ScheduleRun)
        .filter(ScheduleRun.schedule_id == schedule_id)
        .order_by(ScheduleRun.started_at.desc())
        .limit(50)
        .all()
    )


@router.patch("/{schedule_id}/toggle")
def toggle_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schedule = db.query(ScheduledAnalysis).filter(
        ScheduledAnalysis.id == schedule_id,
        ScheduledAnalysis.user_id == user.id,
    ).first()
    if not schedule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schedule not found.")
    schedule.is_active = not schedule.is_active
    db.commit()
    return {"is_active": schedule.is_active}


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schedule = db.query(ScheduledAnalysis).filter(
        ScheduledAnalysis.id == schedule_id,
        ScheduledAnalysis.user_id == user.id,
    ).first()
    if not schedule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schedule not found.")
    db.delete(schedule)
    db.commit()
