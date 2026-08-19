"""Ties the whole deterministic profiling pipeline together."""
from __future__ import annotations

import time
from typing import Any

import pandas as pd

from app.profiling.column_profiler import profile_column
from app.profiling.correlation import DEFAULT_HIGH_CORR_THRESHOLD, analyze_correlations
from app.profiling.leakage import detect_potential_leakage
from app.profiling.loader import LoadedDataset
from app.profiling.outliers import detect_outliers
from app.profiling.quality import detect_quality_issues
from app.profiling.readiness_score import apply_leakage_penalty, compute_ml_readiness_score
from app.profiling.target_detection import detect_target_column, evaluate_class_imbalance


def run_full_profile(
    loaded: LoadedDataset,
    correlation_threshold: float = DEFAULT_HIGH_CORR_THRESHOLD,
    manual_target: str | None = None,
) -> dict[str, Any]:
    start = time.perf_counter()
    df: pd.DataFrame = loaded.df
    total_rows, total_cols = df.shape

    column_profiles = [profile_column(df[col], col, total_rows) for col in df.columns]

    quality_result = detect_quality_issues(df, column_profiles)
    outliers = detect_outliers(df, column_profiles)
    correlation_result = analyze_correlations(df, column_profiles, threshold=correlation_threshold)
    target_result = detect_target_column(df, column_profiles)

    if manual_target and manual_target in df.columns:
        target_result["most_likely_target"] = manual_target
        target_result["confidence"] = 1.0
        target_result["note"] = "Target column manually selected by user."
        vc = df[manual_target].dropna().astype(str).value_counts(normalize=True)
        if vc.shape[0] <= 20:
            target_result["class_balance"] = {str(k): round(float(v), 4) for k, v in vc.items()}

    class_imbalance = evaluate_class_imbalance(target_result.get("class_balance"))
    leakage_warnings = detect_potential_leakage(target_result, correlation_result, column_profiles)

    readiness = compute_ml_readiness_score(
        column_profiles, quality_result, correlation_result, target_result,
        outliers, class_imbalance, total_rows,
    )
    readiness = apply_leakage_penalty(readiness, leakage_warnings)

    quality_score = _compute_quality_score(quality_result, column_profiles)

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    dtype_counts: dict[str, int] = {}
    for cp in column_profiles:
        dtype_counts[cp["dtype"]] = dtype_counts.get(cp["dtype"], 0) + 1

    return {
        "dataset_overview": {
            "rows": total_rows,
            "columns": total_cols,
            "dtype_counts": dtype_counts,
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1_000_000, 2),
        },
        "column_profiles": column_profiles,
        "quality": quality_result,
        "outliers": outliers,
        "correlation": correlation_result,
        "target": target_result,
        "class_imbalance": class_imbalance,
        "leakage_warnings": leakage_warnings,
        "ml_readiness": readiness,
        "quality_score": quality_score,
        "processing_time_ms": elapsed_ms,
    }


def _compute_quality_score(quality_result: dict[str, Any], column_profiles: list[dict[str, Any]]) -> float:
    """A simpler, separate 'data quality score' (distinct from ML readiness)."""
    n_cols = max(len(column_profiles), 1)
    avg_missing = sum(cp["missing_percentage"] for cp in column_profiles) / n_cols
    dup_pct = quality_result.get("duplicate_row_percentage", 0)
    critical_issues = sum(1 for i in quality_result["issues"] if i["severity"] == "CRITICAL")
    high_issues = sum(1 for i in quality_result["issues"] if i["severity"] == "HIGH")
    score = 100 - avg_missing - (dup_pct * 2) - (critical_issues * 10) - (high_issues * 4)
    return round(max(0, min(100, score)), 1)
