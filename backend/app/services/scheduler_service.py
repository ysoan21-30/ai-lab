"""Scheduled analysis service — manages recurring profiling jobs and alerts."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.models import (
    AnalysisStatus, DatabaseConnection, ScheduleFrequency,
    ScheduleRun, ScheduledAnalysis,
)
from app.services.db_connector import run_query
from app.services.notification_service import send_alert

logger = logging.getLogger(__name__)


def _next_run(frequency: ScheduleFrequency, from_time: datetime | None = None) -> datetime:
    """Calculate next run time based on frequency."""
    now = from_time or datetime.utcnow()
    deltas = {
        ScheduleFrequency.HOURLY: timedelta(hours=1),
        ScheduleFrequency.DAILY: timedelta(days=1),
        ScheduleFrequency.WEEKLY: timedelta(weeks=1),
        ScheduleFrequency.MONTHLY: timedelta(days=30),
    }
    return now + deltas.get(frequency, timedelta(days=1))


def create_schedule(db: Session, schedule: ScheduledAnalysis) -> ScheduledAnalysis:
    """Persist a new schedule and set the initial next_run_at."""
    schedule.next_run_at = _next_run(schedule.frequency)
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def get_due_schedules(db: Session) -> list[ScheduledAnalysis]:
    """Return all active schedules whose next_run_at is in the past."""
    now = datetime.utcnow()
    return (
        db.query(ScheduledAnalysis)
        .filter(
            ScheduledAnalysis.is_active == True,
            ScheduledAnalysis.next_run_at <= now,
        )
        .all()
    )


def execute_scheduled_run(db: Session, schedule: ScheduledAnalysis) -> ScheduleRun:
    """Execute one run of a scheduled analysis.

    For database sources, fetches data via the connector and runs the profiling pipeline.
    Returns the ScheduleRun record.
    """
    run = ScheduleRun(schedule_id=schedule.id, status=AnalysisStatus.PROCESSING)
    db.add(run)
    db.commit()

    try:
        if schedule.source_type == "database" and schedule.connection_id:
            conn = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == schedule.connection_id
            ).first()
            if not conn:
                raise ValueError("Database connection not found")
            if not schedule.query:
                raise ValueError("No query specified for database schedule")

            df = run_query(conn, schedule.query)

            # Run the profiling pipeline on the DataFrame
            from app.profiling.orchestrator import run_full_profile
            from app.profiling.loader import LoadedDataset

            loaded = LoadedDataset(
                df=df,
                original_filename=f"scheduled_{schedule.name}",
                file_size_bytes=0,
                detected_format="database",
            )
            profile = run_full_profile(loaded)

            # Check alert thresholds
            alerts = _check_alerts(db, schedule, profile)

            run.status = AnalysisStatus.COMPLETED
            run.alerts_triggered = alerts if alerts else None
            run.completed_at = datetime.utcnow()

        else:
            # Upload-based schedules need a file — mark as pending for user action
            run.status = AnalysisStatus.PENDING
            run.completed_at = datetime.utcnow()

    except Exception as e:
        logger.exception("Scheduled run failed for %s: %s", schedule.id, e)
        run.status = AnalysisStatus.FAILED
        run.error_message = str(e)
        run.completed_at = datetime.utcnow()

    # Update schedule timing
    schedule.last_run_at = datetime.utcnow()
    schedule.next_run_at = _next_run(schedule.frequency)
    db.commit()
    db.refresh(run)
    return run


def _check_alerts(
    db: Session,
    schedule: ScheduledAnalysis,
    profile: dict,
) -> list[dict]:
    """Compare current profile against alert thresholds, dispatch notifications."""
    alerts = []
    quality_score = profile.get("quality_score", 1.0)
    row_count = profile.get("dataset_overview", {}).get("rows", 0)

    # Get previous run for comparison
    prev_run = (
        db.query(ScheduleRun)
        .filter(
            ScheduleRun.schedule_id == schedule.id,
            ScheduleRun.status == AnalysisStatus.COMPLETED,
        )
        .order_by(ScheduleRun.completed_at.desc())
        .first()
    )

    if schedule.alert_on_quality_drop and quality_score < (1.0 - schedule.alert_on_quality_drop):
        alert = {
            "type": "quality_drop",
            "message": f"Quality score dropped to {quality_score:.1%} (threshold: {schedule.alert_on_quality_drop:.0%} drop)",
            "severity": schedule.alert_severity.value,
        }
        alerts.append(alert)

    if schedule.alert_on_row_count_change and prev_run:
        # Compare with previous row count if available
        pass  # Would need to store row count in run — simplified for MVP

    # Dispatch alerts
    if alerts and schedule.alert_channels:
        for alert in alerts:
            send_alert(
                channels=schedule.alert_channels,
                subject=f"Alert: {schedule.name}",
                message=alert["message"],
            )

    return alerts
