"""Admin dashboard endpoints. Never exposes raw dataset contents."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.billing.plans import get_plan_config
from app.db.session import get_db
from app.models.models import Analysis, AnalysisStatus, PlanTier, User

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def admin_overview(_: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_since = datetime.utcnow() - timedelta(days=30)
    active_users = (
        db.query(func.count(func.distinct(Analysis.user_id)))
        .filter(Analysis.created_at >= active_since)
        .scalar() or 0
    )
    total_analyses = db.query(func.count(Analysis.id)).scalar() or 0
    avg_processing_time = db.query(func.avg(Analysis.processing_time_ms)).filter(
        Analysis.status == AnalysisStatus.COMPLETED
    ).scalar()
    error_count = db.query(func.count(Analysis.id)).filter(Analysis.status == AnalysisStatus.FAILED).scalar() or 0

    plan_counts = dict(
        db.query(User.plan, func.count(User.id)).group_by(User.plan).all()
    )
    plan_counts = {k.value: v for k, v in plan_counts.items()}

    mrr_inr = sum(
        plan_counts.get(tier.value, 0) * get_plan_config(tier)["price_inr"]
        for tier in (PlanTier.PRO, PlanTier.TEAM)
    )

    total_llm_cost = db.query(func.sum(Analysis.llm_cost_usd)).scalar() or 0

    dataset_sizes = db.query(Analysis.row_count).filter(Analysis.row_count.isnot(None)).limit(1000).all()
    buckets = {"<1K rows": 0, "1K-10K": 0, "10K-100K": 0, "100K+": 0}
    for (rows,) in dataset_sizes:
        if rows < 1000:
            buckets["<1K rows"] += 1
        elif rows < 10000:
            buckets["1K-10K"] += 1
        elif rows < 100000:
            buckets["10K-100K"] += 1
        else:
            buckets["100K+"] += 1

    return {
        "total_users": total_users,
        "active_users_30d": active_users,
        "total_analyses": total_analyses,
        "avg_processing_time_ms": round(avg_processing_time, 1) if avg_processing_time else None,
        "error_count": error_count,
        "subscription_counts": plan_counts,
        "estimated_mrr_inr": mrr_inr,
        "total_llm_cost_usd": round(total_llm_cost, 4),
        "dataset_size_distribution": buckets,
    }
