"""Picks which model tier should handle a given request.

Two strategies are provided:

1. `classify_with_model` — asks a cheap model (ROUTER_MODEL) to label the
   request's complexity. Most accurate, costs one small extra call.
2. `classify_with_heuristic` — free, instant, rule-of-thumb based on prompt
   length and a few keyword signals. Good fallback / offline default.

`choose_tier()` tries the heuristic first for obvious cases and only calls
the model classifier when the heuristic is unsure — this keeps routing cheap
on average.
"""

import re

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

from config import DEFAULT_TIER, ROUTER_MODEL, TIERS

_DEEP_SIGNALS = re.compile(
    r"\b(architect|prove|design a system|trade-?off|root cause|debug (a|the) "
    r"(complex|subtle)|optimi[sz]e|strategy|multi-step plan|research paper)\b",
    re.IGNORECASE,
)
_FAST_SIGNALS = re.compile(
    r"^(what is|define|convert|spell|translate|format|list the|what's the "
    r"time|what day)\b",
    re.IGNORECASE,
)


def classify_with_heuristic(prompt: str) -> str | None:
    """Return a tier name for obvious cases, or None if unsure."""
    stripped = prompt.strip()

    if len(stripped) < 60 and _FAST_SIGNALS.search(stripped):
        return "fast"
    if _DEEP_SIGNALS.search(stripped) or len(stripped) > 1200:
        return "deep"
    return None


async def classify_with_model(prompt: str) -> str:
    """Ask a cheap model to label the request's complexity tier.

    Falls back to the default tier on any error — this is a cheap routing
    hint, not something worth failing the whole turn over. In particular:
    an action-sounding prompt (e.g. "Load employees.csv and...") can tempt
    the classifier model into attempting a tool call even with allowed_tools
    disabled; that gets denied, can push the run past max_turns, and the
    underlying CLI process then exits non-zero even after already emitting
    a usable result — the SDK raises in that case, so we catch broadly here.
    """
    tier_list = ", ".join(f"{t.name} ({t.description})" for t in TIERS.values())
    system_prompt = (
        "You are a routing classifier, not an assistant. You must NOT perform, answer, or use "
        "any tools for the request below — you only classify it. Reply with exactly one word — "
        f"the name of the best-fit tier — and nothing else. Tiers: {tier_list}."
    )
    wrapped_prompt = (
        "Classify the complexity of this request (do not fulfill it, do not use tools):\n\n"
        f"{prompt}"
    )

    options = ClaudeAgentOptions(
        model=ROUTER_MODEL,
        system_prompt=system_prompt,
        allowed_tools=[],
        max_turns=2,  # small amount of headroom in case a tool attempt gets denied first
    )

    answer = ""
    try:
        async for message in query(prompt=wrapped_prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        answer += block.text
    except Exception:
        # Routing is best-effort; any SDK/CLI hiccup here shouldn't block the real turn.
        pass

    answer = answer.strip().lower()
    for tier_name in TIERS:
        if tier_name in answer:
            return tier_name
    return DEFAULT_TIER  # safe default if the classifier response is unparseable or failed


async def choose_tier(prompt: str, use_model_classifier: bool = True) -> str:
    heuristic_result = classify_with_heuristic(prompt)
    if heuristic_result is not None:
        return heuristic_result

    if use_model_classifier:
        return await classify_with_model(prompt)

    return DEFAULT_TIER
