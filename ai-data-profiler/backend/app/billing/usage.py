"""Usage tracking and monthly limit enforcement."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.billing.plans import get_plan_config
from app.models.models import Analysis, User, UsageRecord


def get_month_start() -> datetime:
    now = datetime.utcnow()
    return datetime(now.year, now.month, 1)


def get_usage_this_month(db: Session, user: User) -> int:
    month_start = get_month_start()
    return (
        db.query(func.count(UsageRecord.id))
        .filter(UsageRecord.user_id == user.id, UsageRecord.created_at >= month_start)
        .scalar()
        or 0
    )


def enforce_usage_limit(db: Session, user: User) -> None:
    plan_config = get_plan_config(user.plan)
    used = get_usage_this_month(db, user)
    if used >= plan_config["analyses_per_month"]:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"You've reached your monthly limit of {plan_config['analyses_per_month']} "
                f"analyses on the {plan_config['name']} plan. Upgrade your plan to continue."
            ),
        )


def enforce_upload_size(user: User, size_bytes: int) -> int:
    """Returns the max allowed bytes for the user's plan, raising if exceeded."""
    plan_config = get_plan_config(user.plan)
    max_bytes = plan_config["max_upload_mb"] * 1_000_000
    if size_bytes > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File exceeds the {plan_config['max_upload_mb']} MB limit for the "
                f"{plan_config['name']} plan. Upgrade for larger uploads."
            ),
        )
    return max_bytes


def record_usage(
    db: Session, user: User, analysis: Analysis, file_size_bytes: int,
    row_count: int | None, column_count: int | None, processing_time_ms: int | None,
    llm_tokens_used: int | None,
) -> UsageRecord:
    record = UsageRecord(
        user_id=user.id,
        analysis_id=analysis.id,
        file_size_bytes=file_size_bytes,
        row_count=row_count,
        column_count=column_count,
        processing_time_ms=processing_time_ms,
        llm_tokens_used=llm_tokens_used,
        plan=user.plan,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
