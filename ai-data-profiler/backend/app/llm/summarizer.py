"""Builds the reduced, privacy-preserving summary sent to the LLM.

Only aggregated statistics and detected issues are sent -- never raw rows or
individual cell values.
"""
from __future__ import annotations

from typing import Any


def build_llm_summary(profile: dict[str, Any]) -> dict[str, Any]:
    columns_summary = []
    for cp in profile["column_profiles"]:
        entry = {
            "column": cp["column"],
            "dtype": cp["dtype"],
            "missing_percentage": cp["missing_percentage"],
            "unique_percentage": cp["unique_percentage"],
            "is_constant": cp["is_constant"],
            "looks_like_id": cp.get("looks_like_id"),
        }
        if cp["dtype"] == "numeric":
            entry.update({
                "mean": cp.get("mean"), "median": cp.get("median"), "std": cp.get("std"),
                "min": cp.get("min"), "max": cp.get("max"), "skewness": cp.get("skewness"),
            })
        elif cp["dtype"] == "categorical":
            entry.update({
                "cardinality": cp.get("cardinality"),
                "top_values": cp.get("top_values", [])[:3],
            })
        columns_summary.append(entry)

    return {
        "dataset_overview": profile["dataset_overview"],
        "columns": columns_summary,
        "data_quality_issues": [
            {"type": i["type"], "column": i["column"], "severity": i["severity"], "detail": i["detail"]}
            for i in profile["quality"]["issues"][:40]
        ],
        "duplicate_row_percentage": profile["quality"]["duplicate_row_percentage"],
        "outliers": [
            {"column": o["column"], "method": o["method"], "percentage": o["percentage"]}
            for o in profile["outliers"][:20]
        ],
        "high_correlation_pairs": profile["correlation"]["high_correlation_pairs"][:10],
        "target_detection": profile["target"],
        "class_imbalance": profile.get("class_imbalance"),
        "leakage_warnings": [w["message"] for w in profile.get("leakage_warnings", [])],
        "ml_readiness": profile["ml_readiness"],
        "quality_score": profile["quality_score"],
    }
