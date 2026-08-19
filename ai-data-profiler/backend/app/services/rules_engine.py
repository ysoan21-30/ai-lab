"""Custom quality rules engine — evaluates user-defined rules against DataFrames."""
from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from app.models.models import CustomRule, RuleOperator

logger = logging.getLogger(__name__)


def evaluate_rule(rule: CustomRule, df: pd.DataFrame) -> dict:
    """Evaluate a single rule against a DataFrame.

    Returns dict with: rule_id, rule_name, passed, violation_count, violation_sample, message
    """
    result = {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "passed": True,
        "violation_count": 0,
        "violation_sample": [],
        "message": "",
    }

    try:
        op = rule.operator
        col = rule.column_name
        val = rule.value

        if col and col not in df.columns:
            result["passed"] = False
            result["message"] = f"Column '{col}' not found in dataset"
            return result

        if op == RuleOperator.NOT_NULL:
            if col:
                nulls = df[col].isna()
                result["violation_count"] = int(nulls.sum())
                result["passed"] = result["violation_count"] == 0
                if not result["passed"]:
                    result["violation_sample"] = df[nulls].head(5).index.tolist()
                    result["message"] = f"{result['violation_count']} null values found in '{col}'"
            else:
                total_nulls = int(df.isna().sum().sum())
                result["violation_count"] = total_nulls
                result["passed"] = total_nulls == 0
                result["message"] = f"{total_nulls} total null values in dataset"

        elif op == RuleOperator.UNIQUE:
            if not col:
                result["message"] = "UNIQUE rule requires a column name"
                result["passed"] = False
                return result
            dupes = df[col].duplicated(keep=False)
            result["violation_count"] = int(dupes.sum())
            result["passed"] = result["violation_count"] == 0
            if not result["passed"]:
                sample_vals = df[dupes][col].head(5).tolist()
                result["violation_sample"] = sample_vals
                result["message"] = f"{result['violation_count']} duplicate values in '{col}'"

        elif op == RuleOperator.MIN:
            if not col or val is None:
                result["message"] = "MIN rule requires column and threshold value"
                result["passed"] = False
                return result
            threshold = float(val)
            series = pd.to_numeric(df[col], errors="coerce")
            violations = series < threshold
            result["violation_count"] = int(violations.sum())
            result["passed"] = result["violation_count"] == 0
            if not result["passed"]:
                result["violation_sample"] = series[violations].head(5).tolist()
                result["message"] = f"{result['violation_count']} values in '{col}' below {threshold}"

        elif op == RuleOperator.MAX:
            if not col or val is None:
                result["message"] = "MAX rule requires column and threshold value"
                result["passed"] = False
                return result
            threshold = float(val)
            series = pd.to_numeric(df[col], errors="coerce")
            violations = series > threshold
            result["violation_count"] = int(violations.sum())
            result["passed"] = result["violation_count"] == 0
            if not result["passed"]:
                result["violation_sample"] = series[violations].head(5).tolist()
                result["message"] = f"{result['violation_count']} values in '{col}' above {threshold}"

        elif op == RuleOperator.BETWEEN:
            if not col or not isinstance(val, dict):
                result["message"] = "BETWEEN rule requires column and {min, max} value"
                result["passed"] = False
                return result
            low, high = float(val["min"]), float(val["max"])
            series = pd.to_numeric(df[col], errors="coerce")
            violations = (series < low) | (series > high)
            result["violation_count"] = int(violations.sum())
            result["passed"] = result["violation_count"] == 0
            if not result["passed"]:
                result["violation_sample"] = series[violations].head(5).tolist()
                result["message"] = f"{result['violation_count']} values in '{col}' outside [{low}, {high}]"

        elif op == RuleOperator.REGEX:
            if not col or not val:
                result["message"] = "REGEX rule requires column and pattern"
                result["passed"] = False
                return result
            pattern = str(val)
            try:
                re.compile(pattern)
            except re.error:
                result["message"] = f"Invalid regex pattern: {pattern}"
                result["passed"] = False
                return result
            matches = df[col].astype(str).str.match(pattern, na=False)
            violations = ~matches & df[col].notna()
            result["violation_count"] = int(violations.sum())
            result["passed"] = result["violation_count"] == 0
            if not result["passed"]:
                result["violation_sample"] = df[violations][col].head(5).tolist()
                result["message"] = f"{result['violation_count']} values in '{col}' don't match pattern"

        elif op == RuleOperator.IN_LIST:
            if not col or not isinstance(val, list):
                result["message"] = "IN_LIST rule requires column and list of allowed values"
                result["passed"] = False
                return result
            violations = ~df[col].isin(val) & df[col].notna()
            result["violation_count"] = int(violations.sum())
            result["passed"] = result["violation_count"] == 0
            if not result["passed"]:
                result["violation_sample"] = df[violations][col].head(5).tolist()
                result["message"] = f"{result['violation_count']} values in '{col}' not in allowed list"

        elif op == RuleOperator.CUSTOM_SQL:
            # Custom SQL rules are placeholders — would need a query engine
            result["message"] = "Custom SQL rules require database connection (coming soon)"
            result["passed"] = True

        else:
            result["message"] = f"Unknown operator: {op}"
            result["passed"] = False

    except Exception as e:
        logger.exception("Error evaluating rule %s: %s", rule.name, e)
        result["passed"] = False
        result["message"] = f"Rule evaluation error: {e}"

    return result


def evaluate_rules(rules: list[CustomRule], df: pd.DataFrame) -> list[dict]:
    """Evaluate multiple rules against a DataFrame."""
    return [evaluate_rule(r, df) for r in rules if r.is_active]
