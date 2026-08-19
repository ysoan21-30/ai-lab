"""Orchestrates the full pipeline: load -> profile -> LLM insights -> persist."""
from __future__ import annotations

import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.llm.insight_generator import generate_ai_insights
from app.llm.summarizer import build_llm_summary
from app.models.models import Analysis, AnalysisStatus
from app.profiling.loader import DatasetLoadError, LoadedDataset, load_dataset
from app.profiling.orchestrator import run_full_profile
from app.services.charts import build_charts

logger = logging.getLogger(__name__)


def process_upload(
    db: Session,
    analysis: Analysis,
    raw_bytes: bytes,
    filename: str,
    max_size_bytes: int,
    manual_target: str | None = None,
) -> Analysis:
    start = time.perf_counter()
    try:
        loaded: LoadedDataset = load_dataset(raw_bytes, filename, max_size_bytes)
        profile = run_full_profile(loaded, manual_target=manual_target)
        llm_summary = build_llm_summary(profile)
        ai_insights = generate_ai_insights(llm_summary)
        charts = build_charts(profile)

        analysis.status = AnalysisStatus.COMPLETED
        analysis.row_count = profile["dataset_overview"]["rows"]
        analysis.column_count = profile["dataset_overview"]["columns"]
        analysis.profile_result = {"column_profiles": profile["column_profiles"], "dataset_overview": profile["dataset_overview"]}
        analysis.quality_result = profile["quality"]
        analysis.correlation_result = profile["correlation"]
        analysis.target_result = {
            **profile["target"],
            "class_imbalance": profile.get("class_imbalance"),
            "leakage_warnings": profile.get("leakage_warnings"),
            "outliers": profile.get("outliers"),
        }
        analysis.ml_readiness_result = profile["ml_readiness"]
        analysis.ai_insights = ai_insights
        analysis.charts = charts
        analysis.quality_score = profile["quality_score"]
        analysis.ml_readiness_score = profile["ml_readiness"]["overall_score"]
        analysis.issue_count = profile["quality"]["total_issues"]
        analysis.llm_tokens_used = ai_insights.get("_meta", {}).get("tokens_used", 0)
        analysis.llm_cost_usd = ai_insights.get("_meta", {}).get("estimated_cost_usd", 0)
        analysis.processing_time_ms = int((time.perf_counter() - start) * 1000)
        analysis.completed_at = datetime.utcnow()

    except DatasetLoadError as exc:
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = str(exc)
    except Exception as exc:  # noqa: BLE001 - never let a bad dataset crash the API
        logger.exception("Unexpected error while processing analysis %s: %s", analysis.id, exc)
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = (
            "An unexpected error occurred while analyzing this dataset. "
            "Our team has been notified. Please try again or use a different file."
        )

    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis
