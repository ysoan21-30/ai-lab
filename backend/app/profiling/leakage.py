"""Heuristic potential data-leakage detection.

Deliberately conservative: never claims definite leakage, only flags
statistical patterns worth a human's attention.
"""
from __future__ import annotations

from typing import Any


def detect_potential_leakage(
    target_info: dict[str, Any],
    correlation_result: dict[str, Any],
    column_profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    target_col = target_info.get("most_likely_target")
    if not target_col:
        return warnings

    pearson = correlation_result.get("pearson", {})
    target_corrs = pearson.get(target_col, {})
    for other_col, corr in target_corrs.items():
        if other_col == target_col or corr is None:
            continue
        if abs(corr) >= 0.98:
            warnings.append({
                "column": other_col,
                "target": target_col,
                "signal": f"near-perfect correlation with target (r={round(corr, 3)})",
                "message": (
                    f"Potential data leakage detected: '{other_col}' is almost perfectly "
                    f"correlated with the likely target '{target_col}'. This may mean the "
                    f"column is derived from the target, or was recorded after the outcome "
                    f"occurred. Verify before including it as a feature."
                ),
            })

    # Name-based leakage hints: columns whose names suggest they encode outcome info
    suspicious_name_fragments = ["result", "outcome", "final", "post_", "after_"]
    for cp in column_profiles:
        col = cp["column"]
        if col == target_col:
            continue
        lower = col.lower()
        if any(frag in lower for frag in suspicious_name_fragments):
            warnings.append({
                "column": col,
                "target": target_col,
                "signal": "column name suggests it may be recorded after the target outcome",
                "message": (
                    f"Potential data leakage detected: column name '{col}' suggests it might "
                    f"be known only after the outcome occurs. Confirm this data would be "
                    f"available at prediction time."
                ),
            })

    return warnings
