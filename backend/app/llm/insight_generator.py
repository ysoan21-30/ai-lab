"""Generates AI insights from a deterministic analysis summary.

If OPENAI_API_KEY is not configured, falls back to a deterministic
rules-based summary so the product remains fully functional without an
LLM key (per engineering rule: no fake/mocked integrations -- this is a
documented, real fallback path, not a mock).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

# Approximate OpenAI pricing for gpt-4o-mini (USD per 1K tokens) - used only
# for cost estimation in the admin analytics dashboard. Update if pricing changes.
_INPUT_COST_PER_1K = 0.00015
_OUTPUT_COST_PER_1K = 0.0006


def generate_ai_insights(summary: dict[str, Any]) -> dict[str, Any]:
    if settings.openai_api_key:
        try:
            return _generate_with_openai(summary)
        except Exception as exc:  # noqa: BLE001 - never let LLM failure break the report
            logger.exception("LLM insight generation failed, falling back to rules-based summary: %s", exc)
            return _fallback_insights(summary, error=str(exc))
    return _fallback_insights(summary)


def _generate_with_openai(summary: dict[str, Any]) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(summary)},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=1600,
    )
    content = response.choices[0].message.content
    parsed = json.loads(content)

    usage = response.usage
    tokens_used = usage.total_tokens if usage else 0
    cost = 0.0
    if usage:
        cost = (usage.prompt_tokens / 1000 * _INPUT_COST_PER_1K) + \
               (usage.completion_tokens / 1000 * _OUTPUT_COST_PER_1K)

    parsed["_meta"] = {
        "source": "openai",
        "model": settings.openai_model,
        "tokens_used": tokens_used,
        "estimated_cost_usd": round(cost, 6),
    }
    return parsed


def _fallback_insights(summary: dict[str, Any], error: str | None = None) -> dict[str, Any]:
    """Deterministic, rules-based narrative when no LLM key is configured or on failure.

    This is a real, working code path -- not a mock -- and produces genuinely
    useful output derived directly from the analysis, just without LLM prose.
    """
    issues = summary.get("data_quality_issues", [])
    critical = [i for i in issues if i["severity"] in ("CRITICAL", "HIGH")]
    readiness = summary.get("ml_readiness", {})
    overview = summary.get("dataset_overview", {})

    exec_summary = (
        f"This dataset has {overview.get('rows', 0):,} rows and {overview.get('columns', 0)} columns. "
        f"The ML Readiness Score is {readiness.get('overall_score', 'N/A')}/100. "
        f"{len(critical)} high-severity issue(s) were detected out of {len(issues)} total findings."
    )

    top_issues = [
        {"title": f"{i['type'].replace('_', ' ').title()} in '{i['column']}'" if i["column"] else i["type"].replace("_", " ").title(),
         "explanation": i["detail"]}
        for i in issues[:5]
    ]
    critical_issues = [
        {"title": f"{i['type'].replace('_', ' ').title()} in '{i['column']}'" if i["column"] else i["type"].replace("_", " ").title(),
         "explanation": i["detail"]}
        for i in critical[:5]
    ]

    cleaning_steps = []
    seen_types = set()
    for i in issues:
        if i["type"] in seen_types:
            continue
        seen_types.add(i["type"])
        cleaning_steps.append(f"{i['detail']} -- {i.get('recommendation', 'Review and address.')}")
        if len(cleaning_steps) >= 6:
            break

    feature_suggestions = []
    high_card = [i for i in issues if i["type"] == "high_cardinality"]
    if high_card:
        feature_suggestions.append("Consider target/frequency encoding for high-cardinality categorical columns.")
    if summary.get("high_correlation_pairs"):
        feature_suggestions.append("Consider dropping or combining highly correlated features to reduce redundancy.")
    if not feature_suggestions:
        feature_suggestions.append("No major feature engineering red flags detected by the deterministic analysis.")

    modeling_concerns = []
    if summary.get("class_imbalance"):
        modeling_concerns.append(
            f"Target class imbalance detected ({summary['class_imbalance']['severity']}); "
            "consider resampling or class weighting."
        )
    if readiness.get("overall_score", 100) < 60:
        modeling_concerns.append("Overall ML readiness is below 60/100 -- address high-severity issues before modeling.")

    leakage_warnings = summary.get("leakage_warnings", [])

    next_steps = [
        "Address CRITICAL and HIGH severity data quality issues first.",
        "Confirm the detected target column manually if one is planned for supervised learning.",
        "Review flagged outliers and correlated feature pairs before feature selection.",
    ]
    if leakage_warnings:
        next_steps.insert(0, "Investigate potential data leakage warnings before training any model.")

    return {
        "executive_summary": exec_summary,
        "top_issues": top_issues,
        "critical_issues": critical_issues,
        "recommended_cleaning_steps": cleaning_steps,
        "feature_engineering_suggestions": feature_suggestions,
        "potential_modeling_concerns": modeling_concerns,
        "leakage_warnings": leakage_warnings,
        "recommended_next_steps": next_steps,
        "_meta": {
            "source": "fallback_rules_based",
            "reason": "OPENAI_API_KEY not configured" if not error else f"LLM error: {error}",
            "tokens_used": 0,
            "estimated_cost_usd": 0,
        },
    }
