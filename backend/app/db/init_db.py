"""Creates all tables and seeds default plan rows.

For this MVP we use SQLAlchemy's create_all instead of a full Alembic
migration history to keep local setup to a single command. Alembic is
included in requirements.txt so migrations can be introduced once the
schema needs versioned changes in production.
"""
import logging

from app.billing.plans import PLAN_DEFAULTS
from app.db.session import Base, SessionLocal, engine
from app.models import models  # noqa: F401 - ensures models are registered on Base

logger = logging.getLogger(__name__)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _seed_plans()


def _seed_plans() -> None:
    db = SessionLocal()
    try:
        for tier, config in PLAN_DEFAULTS.items():
            existing = db.query(models.Plan).filter(models.Plan.tier == tier).first()
            if existing:
                continue
            db.add(models.Plan(
                tier=tier,
                name=config["name"],
                price_inr=config["price_inr"],
                analyses_per_month=config["analyses_per_month"],
                max_upload_mb=config["max_upload_mb"],
                features=config["features"],
            ))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized and plans seeded.")
