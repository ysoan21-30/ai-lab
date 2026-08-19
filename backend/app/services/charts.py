"""Builds lightweight chart-ready JSON (consumed by Plotly on the frontend).

Kept intentionally small: only the charts that support decisions, not dozens
of redundant plots.
"""
from __future__ import annotations

from typing import Any


def build_charts(profile: dict[str, Any]) -> dict[str, Any]:
    charts: dict[str, Any] = {}

    # Missing values bar chart
    missing = [
        {"column": cp["column"], "missing_percentage": cp["missing_percentage"]}
        for cp in profile["column_profiles"] if cp["missing_percentage"] > 0
    ]
    missing.sort(key=lambda x: x["missing_percentage"], reverse=True)
    charts["missing_values"] = missing[:25]

    # Cardinality chart (categorical columns)
    cardinality = [
        {"column": cp["column"], "cardinality": cp.get("cardinality", cp["unique_count"])}
        for cp in profile["column_profiles"] if cp["dtype"] == "categorical"
    ]
    cardinality.sort(key=lambda x: x["cardinality"], reverse=True)
    charts["cardinality"] = cardinality[:20]

    # Numeric distributions (histogram-ready summary stats, top 6 by variance signal)
    numeric_cols = [cp for cp in profile["column_profiles"] if cp["dtype"] == "numeric"]
    numeric_cols.sort(key=lambda cp: (cp.get("std") or 0), reverse=True)
    charts["numeric_distributions"] = [
        {
            "column": cp["column"],
            "min": cp.get("min"), "max": cp.get("max"), "mean": cp.get("mean"),
            "median": cp.get("median"), "quantiles": cp.get("quantiles"),
        }
        for cp in numeric_cols[:8]
    ]

    # Class distribution for detected target
    target_col = profile.get("target", {}).get("most_likely_target")
    class_balance = profile.get("target", {}).get("class_balance")
    if target_col and class_balance:
        charts["class_distribution"] = {
            "column": target_col,
            "distribution": [{"class": k, "proportion": v} for k, v in class_balance.items()],
        }

    # Correlation heatmap (numeric columns only, capped for readability)
    pearson = profile.get("correlation", {}).get("pearson", {})
    cols = list(pearson.keys())[:20]
    if cols:
        charts["correlation_heatmap"] = {
            "columns": cols,
            "matrix": [[pearson[c].get(r) for r in cols] for c in cols],
        }

    # Outlier summary chart
    outliers = profile.get("outliers", [])
    outlier_summary: dict[str, int] = {}
    for o in outliers:
        outlier_summary[o["column"]] = max(outlier_summary.get(o["column"], 0), o["count"])
    charts["outliers"] = [{"column": k, "count": v} for k, v in
                           sorted(outlier_summary.items(), key=lambda x: x[1], reverse=True)[:15]]

    return charts
