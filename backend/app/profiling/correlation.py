"""Correlation analysis for numerical features."""
from __future__ import annotations

from typing import Any

import pandas as pd

DEFAULT_HIGH_CORR_THRESHOLD = 0.90


def analyze_correlations(
    df: pd.DataFrame,
    column_profiles: list[dict[str, Any]],
    threshold: float = DEFAULT_HIGH_CORR_THRESHOLD,
) -> dict[str, Any]:
    # Include boolean columns alongside numeric ones: a 0/1-coded column
    # (very commonly the target in a binary classification dataset) is
    # classified as dtype "boolean" by column_profiler, but Pearson
    # correlation against a binary variable (point-biserial correlation) is
    # well-defined and standard practice. Excluding it here would silently
    # disable correlation-based leakage detection for the most common
    # target format.
    numeric_cols = [
        cp["column"] for cp in column_profiles
        if cp["dtype"] in ("numeric", "boolean") and not cp["is_constant"]
    ]
    if len(numeric_cols) < 2:
        return {
            "numeric_columns_used": numeric_cols,
            "pearson": {},
            "spearman": {},
            "high_correlation_pairs": [],
            "threshold": threshold,
        }

    numeric_df = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    pearson = numeric_df.corr(method="pearson")
    spearman = numeric_df.corr(method="spearman")

    high_pairs = []
    seen = set()
    for col_a in numeric_cols:
        for col_b in numeric_cols:
            if col_a == col_b or (col_b, col_a) in seen:
                continue
            seen.add((col_a, col_b))
            p_val = pearson.loc[col_a, col_b]
            if pd.notna(p_val) and abs(p_val) >= threshold:
                high_pairs.append({
                    "column_a": col_a,
                    "column_b": col_b,
                    "pearson": round(float(p_val), 4),
                    "spearman": round(float(spearman.loc[col_a, col_b]), 4) if pd.notna(spearman.loc[col_a, col_b]) else None,
                    "explanation": (
                        f"'{col_a}' and '{col_b}' are highly correlated (r={round(float(p_val), 2)}). "
                        "This can indicate multicollinearity or redundant features -- consider "
                        "dropping one, combining them, or using regularization (e.g. Ridge/Lasso)."
                    ),
                })

    high_pairs.sort(key=lambda p: abs(p["pearson"]), reverse=True)

    return {
        "numeric_columns_used": numeric_cols,
        "pearson": _matrix_to_json(pearson),
        "spearman": _matrix_to_json(spearman),
        "high_correlation_pairs": high_pairs,
        "threshold": threshold,
    }


def _matrix_to_json(matrix: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    matrix = matrix.round(4)
    return {
        col: {row: (None if pd.isna(v) else float(v)) for row, v in matrix[col].items()}
        for col in matrix.columns
    }
