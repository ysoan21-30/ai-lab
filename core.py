"""
Core turn-runner shared by both interfaces (rich terminal REPL and the
Streamlit web UI).

Exposes `run_turn()`: sends one prompt to the SDK, streams text back through
callbacks as it arrives, and returns the full result. Conversation
continuity across turns is done via `resume=<session_id>` rather than
`ClaudeSDKClient`, because we want to be able to swap the model tier on
every single turn — `ClaudeSDKClient` locks the model for the life of the
client.
"""

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)
from claude_agent_sdk.types import StreamEvent

from config import DEFAULT_TIER, TIERS
from router import choose_tier
from tools import ALLOWED_TOOL_NAMES, tools_server

SYSTEM_PROMPT = (
    "You are a data science assistant. Your job is to help build better datasets, "
    "engineer good features, and do thorough exploratory data analysis (EDA).\n\n"
    "Working style:\n"
    "- When given a new dataset, start with load_dataset to profile it (shape, dtypes, "
    "nulls, duplicates, summary stats, top categorical values) before doing anything else.\n"
    "- Use python_exec for actual analysis, feature engineering, and plotting (pandas/numpy/"
    "matplotlib/scikit-learn/scipy are available). Save plots with plt.savefig(...) so they "
    "persist in the workspace; print() results you want to report back.\n"
    "- Call out data quality issues proactively: high null rates, class imbalance, leakage risk, "
    "outliers, suspicious duplicates, or columns that look like ID/target leakage.\n"
    "- When suggesting features, explain briefly why each one might help (signal, not just "
    "mechanics).\n"
    "- For questions about docs/pages that have been scraped into the local knowledge base "
    "(via scrape_page/crawl_site), use retrieve_docs to ground your answer instead of relying on "
    "memory — check list_rag_sources first if you're unsure what's been ingested.\n"
    "- Use web_search for quick facts, scrape_page for pulling one page into the permanent doc "
    "store, and crawl_site when the user wants a fuller reference (e.g. a whole docs site) "
    "ingested for later retrieval.\n"
    "- Be concise but show your work: state assumptions, and note when a result depends on "
    "something you couldn't verify (e.g. unclear column semantics)."
)

OnTextDelta = Callable[[str], None]
OnToolCall = Callable[[str, dict], None]


@dataclass
class TurnResult:
    text: str
    tier: str
    model: str
    session_id: Optional[str]
    cost_usd: Optional[float]
    tool_calls: list = field(default_factory=list)
    error: Optional[str] = None


async def run_turn(
    prompt: str,
    session_id: Optional[str] = None,
    force_tier: Optional[str] = None,
    on_text_delta: Optional[OnTextDelta] = None,
    on_tool_call: Optional[OnToolCall] = None,
) -> TurnResult:
    """Run one conversational turn and return the full result.

    If `session_id` is given, the turn resumes that session (conversation
    history carries over) even though the model tier can differ from the
    previous turn.
    """
    tier_name = force_tier or await choose_tier(prompt)
    tier = TIERS.get(tier_name, TIERS[DEFAULT_TIER])

    options = ClaudeAgentOptions(
        model=tier.model,
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"toolbox": tools_server},
        allowed_tools=ALLOWED_TOOL_NAMES,
        permission_mode="acceptEdits",
        include_partial_messages=True,
        resume=session_id,
    )

    full_text = ""
    tool_calls: list = []
    new_session_id = session_id
    cost_usd = None
    error = None

    streamed_any_text = False

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, StreamEvent):
            event = message.event
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    chunk = delta.get("text", "")
                    if chunk:
                        streamed_any_text = True
                        full_text += chunk
                        if on_text_delta:
                            on_text_delta(chunk)

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    tool_calls.append({"name": block.name, "input": block.input})
                    if on_tool_call:
                        on_tool_call(block.name, block.input)
                elif isinstance(block, TextBlock):
                    # Fallback path for when streaming deltas weren't emitted.
                    if not streamed_any_text:
                        full_text += block.text
                        if on_text_delta:
                            on_text_delta(block.text)

        elif isinstance(message, ResultMessage):
            new_session_id = message.session_id
            cost_usd = getattr(message, "total_cost_usd", None)
            if message.subtype != "success":
                error = f"Run failed: {message.subtype}"
            # Last-resort fallback if nothing else produced text.
            if not full_text and isinstance(message.result, str):
                full_text = message.result

    return TurnResult(
        text=full_text,
        tier=tier.name,
        model=tier.model,
        session_id=new_session_id,
        cost_usd=cost_usd,
        tool_calls=tool_calls,
        error=error,
    )
