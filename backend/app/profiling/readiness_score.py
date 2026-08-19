"""ML Readiness Score: a transparent, explainable 0-100 heuristic score.

This is explicitly NOT a model-performance prediction -- it is a proxy for
how much cleanup a dataset needs before it's suitable to model.
"""
from __future__ import annotations

from typing import Any


def _clamp(value: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, value))


def compute_ml_readiness_score(
    column_profiles: list[dict[str, Any]],
    quality_result: dict[str, Any],
    correlation_result: dict[str, Any],
    target_result: dict[str, Any],
    outliers: list[dict[str, Any]],
    class_imbalance: dict[str, Any] | None,
    total_rows: int,
) -> dict[str, Any]:
    n_cols = max(len(column_profiles), 1)

    # --- Data Quality (missing values + duplicates) ---
    avg_missing_pct = sum(cp["missing_percentage"] for cp in column_profiles) / n_cols
    dup_pct = quality_result.get("duplicate_row_percentage", 0)
    data_quality = 100 - _clamp(avg_missing_pct * 1.5) - _clamp(dup_pct * 2)
    data_quality = _clamp(data_quality)

    # --- Feature Quality (constants, near-constants, high cardinality, outliers) ---
    constant_cols = sum(1 for cp in column_profiles if cp["is_constant"])
    near_constant_cols = sum(1 for cp in column_profiles if cp["is_near_constant"])
    high_card_cols = sum(1 for cp in column_profiles if cp.get("high_cardinality"))
    outlier_penalty = min(len({o["column"] for o in outliers}) * 3, 20)
    feature_quality = 100 - (constant_cols / n_cols * 40) - (near_constant_cols / n_cols * 15) \
        - (high_card_cols / n_cols * 15) - outlier_penalty
    feature_quality = _clamp(feature_quality)

    # --- Target Quality ---
    if target_result.get("most_likely_target"):
        target_quality = 70 + target_result.get("confidence", 0) * 30
    else:
        target_quality = 50  # unknown target isn't necessarily bad (unsupervised use case)
    if class_imbalance:
        sev_penalty = {"LOW": 0, "MEDIUM": 15, "HIGH": 30, "CRITICAL": 45}
        target_quality -= sev_penalty.get(class_imbalance["severity"], 0)
    target_quality = _clamp(target_quality)

    # --- Distribution Quality (skew + correlation redundancy) ---
    numeric_profiles = [cp for cp in column_profiles if cp["dtype"] == "numeric"]
    skewed = sum(1 for cp in numeric_profiles if cp.get("skewness") is not None and abs(cp["skewness"]) > 2)
    high_corr_pairs = len(correlation_result.get("high_correlation_pairs", []))
    distribution_quality = 100 - (skewed / max(len(numeric_profiles), 1) * 30) - min(high_corr_pairs * 5, 30)
    distribution_quality = _clamp(distribution_quality)

    # --- Leakage Risk (100 = low risk) handled by caller via penalty argument ---
    leakage_risk = 100  # adjusted by caller if leakage warnings exist

    overall = (
        data_quality * 0.30
        + feature_quality * 0.25
        + target_quality * 0.20
        + distribution_quality * 0.15
        + leakage_risk * 0.10
    )

    return {
        "overall_score": round(_clamp(overall), 1),
        "breakdown": {
            "data_quality": round(data_quality, 1),
            "feature_quality": round(feature_quality, 1),
            "target_quality": round(target_quality, 1),
            "distribution_quality": round(distribution_quality, 1),
            "leakage_risk": round(leakage_risk, 1),
        },
        "methodology": (
            "Weighted heuristic: Data Quality 30% (missing values, duplicates), "
            "Feature Quality 25% (constants, high-cardinality, outliers), "
            "Target Quality 20% (target confidence, class balance), "
            "Distribution Quality 15% (skewness, feature redundancy), "
            "Leakage Risk 10% (potential target leakage signals). "
            "This is a heuristic proxy for modeling readiness, not a prediction of "
            "model accuracy or performance."
        ),
        "disclaimer": "ML Readiness Score is a guideline, not a scientific guarantee of model performance.",
    }


def apply_leakage_penalty(readiness: dict[str, Any], leakage_warnings: list[dict[str, Any]]) -> dict[str, Any]:
    if not leakage_warnings:
        return readiness
    penalty = min(len(leakage_warnings) * 25, 70)
    new_leakage_risk = _clamp(100 - penalty)
    breakdown = readiness["breakdown"]
    breakdown["leakage_risk"] = round(new_leakage_risk, 1)
    overall = (
        breakdown["data_quality"] * 0.30
        + breakdown["feature_quality"] * 0.25
        + breakdown["target_quality"] * 0.20
        + breakdown["distribution_quality"] * 0.15
        + breakdown["leakage_risk"] * 0.10
    )
    readiness["overall_score"] = round(_clamp(overall), 1)
    return readiness
