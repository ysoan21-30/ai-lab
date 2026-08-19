"""Heuristic potential-target-column detection (never silently assumed)."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

TARGET_NAME_HINTS = re.compile(
    r"(^target$|^label$|^class$|^y$|outcome|churn|default|fraud|converted|purchased|"
    r"survived|approved|response|is_[a-z]+|has_[a-z]+)",
    re.IGNORECASE,
)


def detect_target_column(df: pd.DataFrame, column_profiles: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    total_rows = len(df)

    for cp in column_profiles:
        col = cp["column"]
        score = 0.0
        reasons = []

        if TARGET_NAME_HINTS.search(col):
            score += 0.4
            reasons.append("column name matches common target naming patterns")

        if cp.get("looks_like_id"):
            continue  # IDs are never targets

        if cp["dtype"] in ("categorical", "boolean"):
            cardinality = cp.get("cardinality", cp.get("unique_count", 0))
            if 2 <= cardinality <= 20:
                score += 0.3
                reasons.append(f"low-cardinality categorical ({cardinality} classes), typical of a classification target")
        elif cp["dtype"] == "numeric":
            if cp.get("unique_count", 0) <= 10 and cp.get("unique_count", 0) >= 2:
                score += 0.15
                reasons.append("small number of distinct numeric values, could be a class label")
            else:
                score += 0.1
                reasons.append("continuous numeric column, could be a regression target")

        # Being one of the last columns is a weak positional signal
        position = list(df.columns).index(col)
        if position >= len(df.columns) - 3:
            score += 0.1
            reasons.append("appears near the end of the dataset (common target position)")

        if score > 0:
            candidates.append({
                "column": col,
                "confidence": round(min(score, 1.0), 2),
                "reasons": reasons,
                "dtype": cp["dtype"],
            })

    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    top = candidates[0] if candidates else None

    class_balance = None
    if top and top["dtype"] in ("categorical", "boolean") and top["column"] in df.columns:
        vc = df[top["column"]].dropna().astype(str).value_counts(normalize=True)
        class_balance = {str(k): round(float(v), 4) for k, v in vc.items()}

    return {
        "candidates": candidates[:5],
        "most_likely_target": top["column"] if top and top["confidence"] >= 0.4 else None,
        "confidence": top["confidence"] if top else 0,
        "note": "Potential target detected using heuristics only -- always confirm manually before modeling.",
        "class_balance": class_balance,
    }


def evaluate_class_imbalance(class_balance: dict[str, float] | None) -> dict[str, Any] | None:
    if not class_balance or len(class_balance) < 2:
        return None
    proportions = sorted(class_balance.values(), reverse=True)
    majority, minority = proportions[0], proportions[-1]
    ratio = round(majority / minority, 2) if minority > 0 else float("inf")
    if ratio >= 20:
        severity = "CRITICAL"
    elif ratio >= 10:
        severity = "HIGH"
    elif ratio >= 3:
        severity = "MEDIUM"
    else:
        severity = "LOW"
    return {
        "majority_class_ratio": majority,
        "minority_class_ratio": minority,
        "imbalance_ratio": ratio,
        "severity": severity,
        "recommendation": (
            "Consider resampling (SMOTE/undersampling), class weighting, or "
            "stratified evaluation metrics (F1, PR-AUC) instead of accuracy."
            if severity in ("HIGH", "CRITICAL", "MEDIUM") else
            "Class distribution is reasonably balanced."
        ),
    }
