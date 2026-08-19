"""Dataset comparison: schema diff, distribution shifts, quality deltas."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.profiling.column_profiler import profile_column
from app.profiling.quality import detect_quality_issues


def compare_datasets(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    name_a: str = "Dataset A",
    name_b: str = "Dataset B",
) -> dict[str, Any]:
    """Run a side-by-side comparison of two DataFrames and return a structured diff."""

    # --- Schema comparison ---
    cols_a = set(df_a.columns)
    cols_b = set(df_b.columns)
    common = sorted(cols_a & cols_b)
    only_a = sorted(cols_a - cols_b)
    only_b = sorted(cols_b - cols_a)

    schema_diff = {
        "columns_only_in_a": only_a,
        "columns_only_in_b": only_b,
        "common_columns": common,
        "column_count_a": len(cols_a),
        "column_count_b": len(cols_b),
    }

    # --- Shape comparison ---
    shape = {
        "rows_a": df_a.shape[0],
        "rows_b": df_b.shape[0],
        "row_diff": df_b.shape[0] - df_a.shape[0],
        "row_diff_pct": round((df_b.shape[0] - df_a.shape[0]) / max(df_a.shape[0], 1) * 100, 2),
    }

    # --- Per-column comparison (common columns only) ---
    profiles_a = {col: profile_column(df_a[col], col, df_a.shape[0]) for col in common}
    profiles_b = {col: profile_column(df_b[col], col, df_b.shape[0]) for col in common}

    column_diffs = []
    for col in common:
        pa, pb = profiles_a[col], profiles_b[col]
        diff: dict[str, Any] = {"column": col}

        # Type change
        diff["dtype_a"] = pa["dtype"]
        diff["dtype_b"] = pb["dtype"]
        diff["dtype_changed"] = pa["dtype"] != pb["dtype"]

        # Missing values shift
        diff["missing_pct_a"] = round(pa["missing_percentage"], 2)
        diff["missing_pct_b"] = round(pb["missing_percentage"], 2)
        diff["missing_pct_delta"] = round(pb["missing_percentage"] - pa["missing_percentage"], 2)

        # Unique count shift
        diff["unique_a"] = pa["unique_count"]
        diff["unique_b"] = pb["unique_count"]

        # For numeric columns: compare mean, std, min, max
        if pa["dtype"] == "numeric" and pb["dtype"] == "numeric":
            for stat in ("mean", "std", "min", "max", "median"):
                va = pa.get(stat)
                vb = pb.get(stat)
                diff[f"{stat}_a"] = _safe_round(va)
                diff[f"{stat}_b"] = _safe_round(vb)
                if va is not None and vb is not None and va != 0:
                    diff[f"{stat}_pct_change"] = round((vb - va) / abs(va) * 100, 2)

        # For categorical/text: compare top values
        if pa.get("top_values") and pb.get("top_values"):
            top_a = {tv["value"]: tv["percentage"] for tv in pa["top_values"][:5]}
            top_b = {tv["value"]: tv["percentage"] for tv in pb["top_values"][:5]}
            diff["top_values_a"] = top_a
            diff["top_values_b"] = top_b

        column_diffs.append(diff)

    # --- Quality comparison ---
    quality_a = detect_quality_issues(df_a, list(profiles_a.values()))
    quality_b = detect_quality_issues(df_b, list(profiles_b.values()))

    quality_delta = {
        "issues_a": quality_a["total_issues"],
        "issues_b": quality_b["total_issues"],
        "issues_delta": quality_b["total_issues"] - quality_a["total_issues"],
        "duplicates_pct_a": round(quality_a.get("duplicate_row_percentage", 0), 2),
        "duplicates_pct_b": round(quality_b.get("duplicate_row_percentage", 0), 2),
    }

    # --- Distribution shift detection (numeric columns) ---
    distribution_shifts = []
    for col in common:
        if profiles_a[col]["dtype"] == "numeric" and profiles_b[col]["dtype"] == "numeric":
            series_a = pd.to_numeric(df_a[col], errors="coerce").dropna()
            series_b = pd.to_numeric(df_b[col], errors="coerce").dropna()
            if len(series_a) > 1 and len(series_b) > 1:
                shift = _detect_distribution_shift(series_a, series_b, col)
                if shift:
                    distribution_shifts.append(shift)

    return {
        "name_a": name_a,
        "name_b": name_b,
        "shape": shape,
        "schema_diff": schema_diff,
        "column_diffs": column_diffs,
        "quality_delta": quality_delta,
        "distribution_shifts": distribution_shifts,
    }


def _safe_round(val: Any, digits: int = 4) -> Any:
    if val is None:
        return None
    try:
        return round(float(val), digits)
    except (TypeError, ValueError):
        return val


def _detect_distribution_shift(
    series_a: pd.Series, series_b: pd.Series, col_name: str,
) -> dict[str, Any] | None:
    """Simple distribution shift detection using mean/std comparison + KS-test if scipy available."""
    mean_a, mean_b = series_a.mean(), series_b.mean()
    std_a, std_b = series_a.std(), series_b.std()

    # Cohen's d effect size
    pooled_std = np.sqrt((std_a**2 + std_b**2) / 2) if (std_a + std_b) > 0 else 1.0
    cohens_d = abs(mean_b - mean_a) / pooled_std if pooled_std > 0 else 0

    if cohens_d < 0.2:
        return None  # negligible shift

    result: dict[str, Any] = {
        "column": col_name,
        "mean_a": round(float(mean_a), 4),
        "mean_b": round(float(mean_b), 4),
        "std_a": round(float(std_a), 4),
        "std_b": round(float(std_b), 4),
        "cohens_d": round(float(cohens_d), 4),
        "severity": "HIGH" if cohens_d > 0.8 else "MEDIUM" if cohens_d > 0.5 else "LOW",
    }

    try:
        from scipy.stats import ks_2samp
        stat, p_value = ks_2samp(series_a, series_b)
        result["ks_statistic"] = round(float(stat), 4)
        result["ks_p_value"] = round(float(p_value), 6)
    except ImportError:
        pass

    return result
