"""Dataset comparison endpoint: upload two files and get a side-by-side diff."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.billing.usage import enforce_upload_size
from app.db.session import get_db
from app.models.models import User
from app.profiling.loader import DatasetLoadError, load_dataset
from app.services.comparison import compare_datasets

router = APIRouter(prefix="/api/compare", tags=["comparison"])

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".parquet"}
MAX_FILENAME_LEN = 255


def _validate_ext(filename: str) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type for '{filename}'. Only .csv, .xlsx, and .parquet are supported.",
        )
    return ext


@router.post("")
async def compare_two_datasets(
    file_a: UploadFile,
    file_b: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload two dataset files and receive a structured comparison report."""
    name_a = (file_a.filename or "dataset_a")[:MAX_FILENAME_LEN]
    name_b = (file_b.filename or "dataset_b")[:MAX_FILENAME_LEN]

    _validate_ext(name_a)
    _validate_ext(name_b)

    raw_a = await file_a.read()
    raw_b = await file_b.read()

    max_bytes = enforce_upload_size(user, max(len(raw_a), len(raw_b)))

    try:
        loaded_a = load_dataset(raw_a, name_a, max_bytes)
        loaded_b = load_dataset(raw_b, name_b, max_bytes)
    except DatasetLoadError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    result = compare_datasets(loaded_a.df, loaded_b.df, name_a=name_a, name_b=name_b)
    return result
