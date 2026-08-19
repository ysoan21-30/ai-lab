"""Plan configuration. Defaults come from env vars/settings so pricing isn't
hardcoded throughout the app; the `plans` DB table can override at runtime
via the admin panel (seeded from these defaults on first boot)."""
from __future__ import annotations

from app.core.config import settings
from app.models.models import PlanTier

PLAN_DEFAULTS = {
    PlanTier.FREE: {
        "name": "Free",
        "price_inr": 0,
        "analyses_per_month": settings.free_analyses_per_month,
        "max_upload_mb": settings.max_upload_mb_free,
        "features": [
            "3 analyses / month",
            "Basic profiling & data quality report",
            "Web report viewer",
            "CSV issue export",
        ],
    },
    PlanTier.PRO: {
        "name": "Pro",
        "price_inr": settings.pro_price_inr,
        "analyses_per_month": settings.pro_analyses_per_month,
        "max_upload_mb": settings.max_upload_mb_pro,
        "features": [
            "50 analyses / month",
            "Larger datasets",
            "AI-generated insights",
            "Advanced statistics & correlation analysis",
            "PDF export",
            "Python cleaning recommendation snippets",
        ],
    },
    PlanTier.TEAM: {
        "name": "Team",
        "price_inr": settings.team_price_inr,
        "analyses_per_month": settings.team_analyses_per_month,
        "max_upload_mb": settings.max_upload_mb_team,
        "features": [
            "500 analyses / month",
            "Multiple users",
            "Shared reports",
            "API access",
            "Priority processing",
        ],
    },
}


def get_plan_config(tier: PlanTier) -> dict:
    return PLAN_DEFAULTS[tier]
