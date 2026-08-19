"""Outlier detection using IQR and Z-score methods (report-only, no auto-removal)."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def detect_outliers(df: pd.DataFrame, column_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for cp in column_profiles:
        if cp["dtype"] != "numeric":
            continue
        col = cp["column"]
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 10:
            continue

        iqr_result = _iqr_outliers(series)
        z_result = _zscore_outliers(series)

        for method_result in (iqr_result, z_result):
            if method_result and method_result["count"] > 0:
                results.append({
                    "column": col,
                    "method": method_result["method"],
                    "count": method_result["count"],
                    "percentage": round(method_result["count"] / len(series) * 100, 2),
                    "bounds": method_result.get("bounds"),
                    "potential_impact": _impact_note(method_result["count"] / len(series)),
                    "recommendation": (
                        f"Review outliers in '{col}' before deciding to cap, transform (e.g. log), "
                        f"or remove them. Do not delete automatically without domain justification."
                    ),
                })
    return results


def _iqr_outliers(series: pd.Series) -> dict[str, Any]:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return {"method": "IQR", "count": 0}
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    count = int(((series < lower) | (series > upper)).sum())
    return {"method": "IQR", "count": count, "bounds": {"lower": float(lower), "upper": float(upper)}}


def _zscore_outliers(series: pd.Series, threshold: float = 3.0) -> dict[str, Any]:
    std = series.std()
    if not std or np.isnan(std) or std == 0:
        return {"method": "Z-score", "count": 0}
    z_scores = (series - series.mean()) / std
    count = int((z_scores.abs() > threshold).sum())
    return {"method": "Z-score", "count": count, "bounds": {"threshold": threshold}}


def _impact_note(fraction: float) -> str:
    if fraction < 0.01:
        return "Low impact: a small number of extreme values, unlikely to distort most models significantly."
    if fraction < 0.05:
        return "Moderate impact: could skew mean-based statistics and distance-based models (e.g. KNN, linear regression)."
    return "High impact: a substantial share of values are extreme; consider transformation or robust modeling methods."
