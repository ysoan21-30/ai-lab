"""Safe dataset loading for CSV / XLSX / Parquet with defensive error handling.

Never trusts the file extension alone: sniffs actual content/MIME before
parsing, and never lets a malformed file crash the process.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import pandas as pd

MAX_ROWS_HARD_CAP = 2_000_000
MAX_COLS_HARD_CAP = 2_000

# Apache Parquet magic bytes (first 4 bytes of every valid Parquet file)
_PARQUET_MAGIC = b"PAR1"


class DatasetLoadError(Exception):
    """Raised for any user-facing dataset loading failure."""


@dataclass
class LoadedDataset:
    df: pd.DataFrame
    original_filename: str
    detected_format: str


def _sniff_format(raw: bytes, filename: str) -> str:
    lower = filename.lower()
    # Parquet files start with PAR1 magic bytes
    if raw[:4] == _PARQUET_MAGIC:
        return "parquet"
    # XLSX files are zip archives -> start with PK\x03\x04
    if raw[:4] == b"PK\x03\x04":
        return "xlsx"
    # Extension claims Excel but content isn't a zip -> likely corrupted/mislabeled
    if lower.endswith((".xlsx", ".xls")):
        raise DatasetLoadError(
            "This file has an Excel extension but its contents don't look like a "
            "valid Excel file. It may be corrupted or mislabeled."
        )
    # Extension claims Parquet but magic bytes don't match
    if lower.endswith(".parquet"):
        raise DatasetLoadError(
            "This file has a .parquet extension but its contents don't look like a "
            "valid Parquet file. It may be corrupted or mislabeled."
        )
    return "csv"


def load_dataset(raw: bytes, filename: str, max_size_bytes: int) -> LoadedDataset:
    if not raw:
        raise DatasetLoadError("The uploaded file is empty.")

    if len(raw) > max_size_bytes:
        raise DatasetLoadError(
            f"File is too large ({len(raw) / 1_000_000:.1f} MB). "
            f"Maximum allowed size for your plan is {max_size_bytes / 1_000_000:.0f} MB."
        )

    fmt = _sniff_format(raw, filename)

    try:
        if fmt == "parquet":
            df = pd.read_parquet(io.BytesIO(raw))
        elif fmt == "xlsx":
            df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
        else:
            df = _read_csv_robust(raw)
    except DatasetLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 - convert any parser failure to a safe message
        raise DatasetLoadError(
            "We couldn't parse this file. It may be corrupted, use an unsupported "
            "structure, or not actually be a CSV/XLSX/Parquet file."
        ) from exc

    if df is None or df.shape[1] == 0:
        raise DatasetLoadError("No columns could be detected in this file.")

    if df.shape[0] == 0:
        raise DatasetLoadError("The dataset has no data rows.")

    if df.shape[0] > MAX_ROWS_HARD_CAP:
        raise DatasetLoadError(
            f"Dataset has {df.shape[0]:,} rows, which exceeds the current hard "
            f"limit of {MAX_ROWS_HARD_CAP:,} rows for this MVP."
        )
    if df.shape[1] > MAX_COLS_HARD_CAP:
        raise DatasetLoadError(
            f"Dataset has {df.shape[1]:,} columns, which exceeds the current hard "
            f"limit of {MAX_COLS_HARD_CAP:,} columns for this MVP."
        )

    # Normalize duplicate / unnamed column headers so downstream code never breaks
    df.columns = _dedupe_columns([str(c) for c in df.columns])

    return LoadedDataset(df=df, original_filename=filename, detected_format=fmt)


def _read_csv_robust(raw: bytes) -> pd.DataFrame:
    """Try a few encodings/separators before giving up."""
    last_exc: Optional[Exception] = None
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(
                io.BytesIO(raw),
                encoding=encoding,
                sep=None,
                engine="python",
                on_bad_lines="skip",
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            continue
    raise DatasetLoadError("Unable to parse CSV file with common encodings.") from last_exc


def _dedupe_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for i, col in enumerate(columns):
        name = col.strip() if col and col.strip() else f"unnamed_{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}.{seen[name]}"
        else:
            seen[name] = 0
        result.append(name)
    return result
