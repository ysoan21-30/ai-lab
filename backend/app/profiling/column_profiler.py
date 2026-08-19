"""Per-column statistical profiling."""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

DATE_HINT_RE = re.compile(r"(date|_dt$|^dt_|time|timestamp)", re.IGNORECASE)
ID_HINT_RE = re.compile(r"(^id$|_id$|^id_|uuid|guid|^index$|^key$|_key$)", re.IGNORECASE)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _try_parse_datetime(series: pd.Series) -> pd.Series | None:
    if series.dtype == "datetime64[ns]":
        return series
    if series.dtype != object:
        return None
    sample = series.dropna().astype(str).head(200)
    if sample.empty:
        return None
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    success_rate = parsed.notna().mean()
    if success_rate >= 0.85:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    return None


def classify_dtype(series: pd.Series, col_name: str) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        non_null = series.dropna()
        if non_null.empty:
            return "numeric"
        unique_vals = non_null.unique()
        if len(unique_vals) <= 2 and set(np.round(unique_vals, 6)).issubset({0, 1}):
            return "boolean"
        return "numeric"
    if DATE_HINT_RE.search(col_name) and _try_parse_datetime(series) is not None:
        return "datetime"
    return "categorical"


def profile_column(series: pd.Series, col_name: str, total_rows: int) -> dict[str, Any]:
    missing_count = int(series.isna().sum())
    missing_pct = round(missing_count / total_rows * 100, 2) if total_rows else 0.0
    non_null = series.dropna()
    unique_count = int(non_null.nunique())
    unique_pct = round(unique_count / total_rows * 100, 2) if total_rows else 0.0

    dtype = classify_dtype(series, col_name)

    # Near-constant means one value dominates almost every row -- NOT simply
    # "few unique values relative to row count". The latter would flag every
    # balanced binary/low-cardinality column (e.g. a 50/50 target) as
    # near-constant in any reasonably sized dataset, which is wrong: a
    # column with exactly 2 unique values only carries little signal if one
    # of those values is overwhelmingly dominant.
    dominant_value_fraction = 0.0
    if not non_null.empty:
        dominant_value_fraction = float(non_null.value_counts(normalize=True).iloc[0])

    result: dict[str, Any] = {
        "column": col_name,
        "dtype": dtype,
        "pandas_dtype": str(series.dtype),
        "missing_count": missing_count,
        "missing_percentage": missing_pct,
        "unique_count": unique_count,
        "unique_percentage": unique_pct,
        "is_constant": unique_count <= 1,
        "is_near_constant": unique_count > 1 and dominant_value_fraction >= 0.99,
        "looks_like_id": bool(ID_HINT_RE.search(col_name)) or (total_rows > 20 and unique_pct >= 99.0),
    }

    if dtype == "numeric":
        result.update(_profile_numeric(non_null))
    elif dtype == "categorical":
        result.update(_profile_categorical(non_null, total_rows))
    elif dtype == "datetime":
        parsed = series if pd.api.types.is_datetime64_any_dtype(series) else _try_parse_datetime(series)
        result.update(_profile_datetime(parsed, total_rows))
    elif dtype == "boolean":
        result.update(_profile_categorical(non_null.astype(str), total_rows))

    return result


def _profile_numeric(non_null: pd.Series) -> dict[str, Any]:
    if non_null.empty:
        return {}
    numeric = pd.to_numeric(non_null, errors="coerce").dropna()
    if numeric.empty:
        return {}
    desc = numeric.describe()
    skew = _safe_float(stats.skew(numeric)) if len(numeric) >= 3 else None
    kurt = _safe_float(stats.kurtosis(numeric)) if len(numeric) >= 4 else None
    return {
        "min": _safe_float(desc.get("min")),
        "max": _safe_float(desc.get("max")),
        "mean": _safe_float(desc.get("mean")),
        "median": _safe_float(numeric.median()),
        "std": _safe_float(desc.get("std")),
        "q1": _safe_float(numeric.quantile(0.25)),
        "q3": _safe_float(numeric.quantile(0.75)),
        "quantiles": {
            "p1": _safe_float(numeric.quantile(0.01)),
            "p5": _safe_float(numeric.quantile(0.05)),
            "p25": _safe_float(numeric.quantile(0.25)),
            "p50": _safe_float(numeric.quantile(0.50)),
            "p75": _safe_float(numeric.quantile(0.75)),
            "p95": _safe_float(numeric.quantile(0.95)),
            "p99": _safe_float(numeric.quantile(0.99)),
        },
        "mode": _safe_float(numeric.mode().iloc[0]) if not numeric.mode().empty else None,
        "zero_count": int((numeric == 0).sum()),
        "negative_count": int((numeric < 0).sum()),
        "skewness": skew,
        "kurtosis": kurt,
    }


def _profile_categorical(non_null: pd.Series, total_rows: int) -> dict[str, Any]:
    if non_null.empty:
        return {"top_values": [], "rare_categories": [], "cardinality": 0}
    value_counts = non_null.astype(str).value_counts()
    cardinality = int(value_counts.shape[0])
    top_values = [
        {"value": str(idx), "count": int(cnt), "percentage": round(cnt / total_rows * 100, 2)}
        for idx, cnt in value_counts.head(10).items()
    ]
    rare_threshold = max(1, int(total_rows * 0.01))
    rare = value_counts[value_counts <= rare_threshold]
    rare_categories = [
        {"value": str(idx), "count": int(cnt)} for idx, cnt in rare.head(20).items()
    ]
    return {
        "top_values": top_values,
        "rare_categories": rare_categories,
        "cardinality": cardinality,
        "cardinality_ratio": round(cardinality / total_rows, 4) if total_rows else 0,
        "high_cardinality": total_rows > 0 and (cardinality / total_rows) > 0.5 and cardinality > 50,
    }


def _profile_datetime(parsed: pd.Series | None, total_rows: int) -> dict[str, Any]:
    if parsed is None:
        return {}
    valid = parsed.dropna()
    if valid.empty:
        return {"min_date": None, "max_date": None, "missing_dates": total_rows}
    now = pd.Timestamp.utcnow().tz_localize(None)
    future_dates = int((valid > now).sum())
    very_old = int((valid.dt.year < 1900).sum())
    return {
        "min_date": valid.min().isoformat(),
        "max_date": valid.max().isoformat(),
        "missing_dates": int(parsed.isna().sum()),
        "suspicious_future_dates": future_dates,
        "suspicious_pre_1900_dates": very_old,
        "has_suspicious_date_range": future_dates > 0 or very_old > 0,
    }
