"""Upload / analysis endpoints: create, list, retrieve, set target, export."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.billing.plans import get_plan_config
from app.billing.usage import enforce_upload_size, enforce_usage_limit, get_usage_this_month, record_usage
from app.db.session import get_db
from app.models.models import Analysis, AnalysisStatus, User
from app.schemas.schemas import AnalysisDetail, AnalysisSummary, SetTargetRequest, UsageOut
from app.services.analysis_pipeline import process_upload
from app.services.report_export import export_issues_csv, export_report_pdf

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".parquet"}
MAX_FILENAME_LEN = 255


@router.post("", response_model=AnalysisDetail, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_usage_limit(db, user)

    filename = (file.filename or "upload")[:MAX_FILENAME_LEN]
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Only .csv, .xlsx, and .parquet files are supported.")

    raw = await file.read()
    max_bytes = enforce_upload_size(user, len(raw))

    analysis = Analysis(
        user_id=user.id,
        dataset_name=filename,
        file_size_bytes=len(raw),
        status=AnalysisStatus.PROCESSING,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    analysis = process_upload(db, analysis, raw, filename, max_bytes)

    record_usage(
        db, user, analysis, len(raw), analysis.row_count, analysis.column_count,
        analysis.processing_time_ms, analysis.llm_tokens_used,
    )

    if analysis.status == AnalysisStatus.FAILED:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=analysis.error_message)

    return analysis


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Analysis)
        .filter(Analysis.user_id == user.id)
        .order_by(Analysis.created_at.desc())
        .limit(100)
        .all()
    )


@router.get("/usage", response_model=UsageOut)
def get_usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan_config = get_plan_config(user.plan)
    return UsageOut(
        plan=user.plan.value,
        analyses_used_this_month=get_usage_this_month(db, user),
        analyses_limit=plan_config["analyses_per_month"],
        max_upload_mb=plan_config["max_upload_mb"],
    )


def _get_owned_analysis(analysis_id: str, user: User, db: Session) -> Analysis:
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == user.id).first()
    if not analysis:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Analysis not found.")
    return analysis


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_owned_analysis(analysis_id, user, db)


@router.post("/{analysis_id}/target", response_model=AnalysisDetail)
def set_target(
    analysis_id: str, payload: SetTargetRequest,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    analysis = _get_owned_analysis(analysis_id, user, db)
    if not analysis.profile_result:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Analysis has no profiling results yet.")
    columns = [cp["column"] for cp in analysis.profile_result.get("column_profiles", [])]
    if payload.column not in columns:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Column '{payload.column}' not found in dataset.")

    # Recompute class_balance for the newly selected column from its already-
    # stored per-column profile (top_values), rather than leaving stale data
    # from whatever column was auto-detected before. We can't re-derive this
    # from the original file since it's deleted immediately after processing
    # (see docs/security.md) -- top_values already captures the distribution
    # for categorical/boolean columns, which is all we need here.
    target_profile = next(
        (cp for cp in analysis.profile_result.get("column_profiles", []) if cp["column"] == payload.column),
        None,
    )
    class_balance = None
    if target_profile and target_profile.get("top_values"):
        class_balance = {tv["value"]: round(tv["percentage"] / 100, 4) for tv in target_profile["top_values"]}

    # IMPORTANT: SQLAlchemy does not detect in-place mutation of a JSON
    # column's nested dict/list -- db.commit() would silently no-op and
    # db.refresh() would then revert to the stale DB value. Always assign a
    # *new* dict object to the attribute so the change is tracked.
    previous = analysis.target_result or {}
    analysis.target_result = {
        **previous,
        "most_likely_target": payload.column,
        "confidence": 1.0,
        "note": "Target column manually selected by user.",
        "class_balance": class_balance,
    }
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    analysis = _get_owned_analysis(analysis_id, user, db)
    db.delete(analysis)
    db.commit()


@router.get("/{analysis_id}/export/json")
def export_json(analysis_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    analysis = _get_owned_analysis(analysis_id, user, db)
    detail = AnalysisDetail.model_validate(analysis)
    return detail


@router.get("/{analysis_id}/export/csv")
def export_csv(analysis_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    analysis = _get_owned_analysis(analysis_id, user, db)
    csv_bytes = export_issues_csv({"quality_result": analysis.quality_result})
    return Response(
        content=csv_bytes, media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{analysis.dataset_name}_issues.csv"'},
    )


@router.get("/{analysis_id}/export/pdf")
def export_pdf(analysis_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.plan.value == "free":
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, detail="PDF export requires a Pro or Team plan.")
    analysis = _get_owned_analysis(analysis_id, user, db)
    pdf_bytes = export_report_pdf({
        "dataset_name": analysis.dataset_name,
        "ai_insights": analysis.ai_insights,
        "quality_score": analysis.quality_score,
        "ml_readiness_score": analysis.ml_readiness_score,
        "issue_count": analysis.issue_count,
        "ml_readiness_result": analysis.ml_readiness_result,
        "quality_result": analysis.quality_result,
    })
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{analysis.dataset_name}_report.pdf"'},
    )
