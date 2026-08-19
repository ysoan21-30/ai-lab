"""Data quality issue detection: missing values, duplicates, constants,
inconsistent categoricals, invalid values, ID columns.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

AGE_RE = re.compile(r"age", re.IGNORECASE)
SALARY_RE = re.compile(r"(salary|income|price|cost|amount|revenue)", re.IGNORECASE)
PERCENT_RE = re.compile(r"(percent|pct|rate|ratio)", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def missing_severity(pct: float) -> str:
    if pct == 0:
        return "NONE"
    if pct < 5:
        return "LOW"
    if pct < 20:
        return "MEDIUM"
    if pct < 50:
        return "HIGH"
    return "CRITICAL"


def detect_quality_issues(df: pd.DataFrame, column_profiles: list[dict[str, Any]]) -> dict[str, Any]:
    total_rows = len(df)
    issues: list[dict[str, Any]] = []

    # --- Missing values ---
    for cp in column_profiles:
        if cp["missing_count"] > 0:
            sev = missing_severity(cp["missing_percentage"])
            issues.append({
                "type": "missing_values",
                "column": cp["column"],
                "severity": sev,
                "detail": f"{cp['missing_percentage']}% missing ({cp['missing_count']} of {total_rows} rows).",
                "recommendation": _missing_recommendation(cp),
            })

    # --- Duplicates ---
    exact_dupes = int(df.duplicated(keep="first").sum())
    if exact_dupes > 0:
        issues.append({
            "type": "duplicate_rows",
            "column": None,
            "severity": "HIGH" if exact_dupes / max(total_rows, 1) > 0.05 else "MEDIUM",
            "detail": f"{exact_dupes} exact duplicate rows found ({round(exact_dupes / total_rows * 100, 2)}%).",
            "recommendation": "Review and consider removing exact duplicate rows with df.drop_duplicates().",
        })

    id_columns = [cp["column"] for cp in column_profiles if cp.get("looks_like_id")]
    for id_col in id_columns:
        if id_col in df.columns:
            dupe_ids = int(df[id_col].duplicated(keep=False).sum())
            if dupe_ids > 0:
                issues.append({
                    "type": "duplicate_id_candidates",
                    "column": id_col,
                    "severity": "HIGH",
                    "detail": f"Column '{id_col}' looks like an identifier but has {dupe_ids} duplicated values.",
                    "recommendation": f"Investigate whether '{id_col}' should be unique; duplicated IDs can indicate join errors or duplicate records.",
                })

    # --- Constant / near-constant columns ---
    for cp in column_profiles:
        if cp["is_constant"]:
            issues.append({
                "type": "constant_column",
                "column": cp["column"],
                "severity": "MEDIUM",
                "detail": f"Column '{cp['column']}' has only one unique value and carries no predictive signal.",
                "recommendation": "Consider dropping this column before modeling.",
            })
        elif cp["is_near_constant"]:
            issues.append({
                "type": "near_constant_column",
                "column": cp["column"],
                "severity": "LOW",
                "detail": f"Column '{cp['column']}' is almost constant ({cp['unique_count']} unique values across {total_rows} rows).",
                "recommendation": "Low variance columns rarely help models; consider dropping or investigating.",
            })

    # --- High cardinality ---
    for cp in column_profiles:
        if cp.get("high_cardinality"):
            issues.append({
                "type": "high_cardinality",
                "column": cp["column"],
                "severity": "MEDIUM",
                "detail": f"Column '{cp['column']}' has {cp['cardinality']} unique categories ({round(cp.get('cardinality_ratio', 0) * 100, 1)}% of rows).",
                "recommendation": "Consider target/frequency encoding, hashing, grouping rare categories, or dropping if it's an identifier.",
            })

    # --- Potential ID columns ---
    for cp in column_profiles:
        if cp.get("looks_like_id"):
            issues.append({
                "type": "potential_id_column",
                "column": cp["column"],
                "severity": "LOW",
                "detail": f"Column '{cp['column']}' looks like an identifier (name pattern or near-100% uniqueness).",
                "recommendation": "ID columns typically should be excluded from model features to avoid overfitting/leakage.",
            })

    # --- Inconsistent categorical values (case/whitespace variants) ---
    for cp in column_profiles:
        if cp["dtype"] != "categorical":
            continue
        col = cp["column"]
        series = df[col].dropna().astype(str)
        if series.empty:
            continue
        normalized = series.str.strip().str.lower()
        groups: dict[str, set[str]] = {}
        for raw, norm in zip(series, normalized):
            groups.setdefault(norm, set()).add(raw)
        inconsistent = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
        if inconsistent:
            examples = list(inconsistent.items())[:5]
            issues.append({
                "type": "inconsistent_categorical_values",
                "column": col,
                "severity": "MEDIUM",
                "detail": "Found variant spellings/casing of the same category, e.g. "
                          + "; ".join(f"{k!r} -> {v}" for k, v in examples),
                "recommendation": f"Normalize with df['{col}'] = df['{col}'].str.strip().str.lower(), then map to canonical labels.",
            })

    # --- Invalid values (domain heuristics) ---
    for cp in column_profiles:
        if cp["dtype"] != "numeric":
            continue
        col = cp["column"]
        neg_count = cp.get("negative_count", 0) or 0
        if neg_count > 0 and AGE_RE.search(col):
            issues.append({
                "type": "invalid_value",
                "column": col,
                "severity": "HIGH",
                "detail": f"Column '{col}' looks like an age field but has {neg_count} negative value(s).",
                "recommendation": f"Investigate negative values in '{col}'; ages cannot be negative.",
            })
        if neg_count > 0 and SALARY_RE.search(col):
            issues.append({
                "type": "invalid_value",
                "column": col,
                "severity": "MEDIUM",
                "detail": f"Column '{col}' looks like a monetary field but has {neg_count} negative value(s).",
                "recommendation": f"Verify whether negative values in '{col}' are valid (e.g. refunds) or data errors.",
            })
        if PERCENT_RE.search(col):
            mx = cp.get("max")
            mn = cp.get("min")
            if mx is not None and (mx > 100 or (mn is not None and mn < 0)):
                issues.append({
                    "type": "invalid_value",
                    "column": col,
                    "severity": "MEDIUM",
                    "detail": f"Column '{col}' looks like a percentage but has values outside [0, 100] (min={mn}, max={mx}).",
                    "recommendation": f"Check whether '{col}' should be bounded between 0 and 100.",
                })
        if AGE_RE.search(col) and cp.get("max") is not None and cp["max"] > 130:
            issues.append({
                "type": "invalid_value",
                "column": col,
                "severity": "MEDIUM",
                "detail": f"Column '{col}' has a maximum value of {cp['max']}, which is implausible for an age field.",
                "recommendation": f"Cap or investigate outlier ages in '{col}'.",
            })

    # --- datetime issues ---
    for cp in column_profiles:
        if cp["dtype"] == "datetime" and cp.get("has_suspicious_date_range"):
            issues.append({
                "type": "suspicious_date_range",
                "column": cp["column"],
                "severity": "LOW",
                "detail": f"Column '{cp['column']}' contains future dates or dates before 1900.",
                "recommendation": "Verify date parsing and check source system for invalid timestamps.",
            })

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    issues.sort(key=lambda i: severity_order.get(i["severity"], 4))

    return {
        "total_issues": len(issues),
        "issues": issues,
        "exact_duplicate_rows": exact_dupes,
        "duplicate_row_percentage": round(exact_dupes / total_rows * 100, 2) if total_rows else 0,
    }


def _missing_recommendation(cp: dict[str, Any]) -> str:
    col = cp["column"]
    if cp["dtype"] == "numeric":
        return (
            f"If '{col}' is skewed, consider median imputation: "
            f"df['{col}'] = df['{col}'].fillna(df['{col}'].median()). "
            f"For symmetric distributions, mean imputation may be acceptable."
        )
    if cp["dtype"] == "categorical":
        return (
            f"Consider filling with the mode or an explicit 'Unknown' category: "
            f"df['{col}'] = df['{col}'].fillna('Unknown')."
        )
    if cp["dtype"] == "datetime":
        return f"Investigate why '{col}' has missing dates; forward/backward fill only if temporally valid."
    return f"Review missing values in '{col}' before modeling."
