"""Integration-shaped tests for core.run_turn() and router.classify_with_model(),
with the Claude Agent SDK's query() mocked out so no live API key/network call is needed.
These exercise the message-handling wiring (streaming deltas, tool calls, result assembly)
that pure unit tests on the tools themselves don't cover.

Uses the SDK's own message dataclasses (not custom fakes) since core.py/router.py branch
on isinstance() checks against those exact types.
"""
import asyncio
from unittest.mock import AsyncMock, patch

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock
from claude_agent_sdk.types import StreamEvent


def text_delta_event(text, session_id="sess"):
    return StreamEvent(
        uuid="u1",
        session_id=session_id,
        event={"type": "content_block_delta", "delta": {"type": "text_delta", "text": text}},
    )


def assistant_msg(content, model="claude-sonnet-4-5"):
    return AssistantMessage(content=content, model=model)


def result_msg(session_id, subtype="success", total_cost_usd=0.01, result=None):
    return ResultMessage(
        subtype=subtype,
        duration_ms=100,
        duration_api_ms=90,
        is_error=(subtype != "success"),
        num_turns=1,
        session_id=session_id,
        total_cost_usd=total_cost_usd,
        result=result,
    )


async def _fake_query_stream(events):
    for e in events:
        yield e


class TestRunTurn:
    def test_streams_text_and_returns_result(self):
        import core

        events = [
            text_delta_event("Hel"),
            text_delta_event("lo"),
            result_msg("sess-1", total_cost_usd=0.0123),
        ]

        deltas = []
        with patch("core.query", return_value=_fake_query_stream(events)), \
             patch("core.choose_tier", new=AsyncMock(return_value="fast")):
            result = asyncio.run(
                core.run_turn("hi", on_text_delta=lambda c: deltas.append(c))
            )

        assert result.text == "Hello"
        assert deltas == ["Hel", "lo"]
        assert result.tier == "fast"
        assert result.session_id == "sess-1"
        assert result.cost_usd == 0.0123
        assert result.error is None

    def test_captures_tool_calls(self):
        import core

        events = [
            assistant_msg([ToolUseBlock(id="t1", name="mcp__toolbox__calculator", input={"a": 1})]),
            result_msg("sess-2"),
        ]
        seen = []
        with patch("core.query", return_value=_fake_query_stream(events)), \
             patch("core.choose_tier", new=AsyncMock(return_value="balanced")):
            result = asyncio.run(
                core.run_turn("do a calc", on_tool_call=lambda n, i: seen.append((n, i)))
            )

        assert result.tool_calls == [{"name": "mcp__toolbox__calculator", "input": {"a": 1}}]
        assert seen == [("mcp__toolbox__calculator", {"a": 1})]

    def test_non_success_result_sets_error(self):
        import core

        events = [result_msg("sess-3", subtype="error_max_turns")]
        with patch("core.query", return_value=_fake_query_stream(events)), \
             patch("core.choose_tier", new=AsyncMock(return_value="balanced")):
            result = asyncio.run(core.run_turn("hi"))

        assert result.error == "Run failed: error_max_turns"

    def test_assistant_text_fallback_when_no_stream_events(self):
        """If include_partial_messages didn't emit deltas, AssistantMessage TextBlocks
        should still be captured as a fallback."""
        import core

        events = [
            assistant_msg([TextBlock(text="fallback answer")]),
            result_msg("sess-4"),
        ]
        with patch("core.query", return_value=_fake_query_stream(events)), \
             patch("core.choose_tier", new=AsyncMock(return_value="balanced")):
            result = asyncio.run(core.run_turn("hi"))

        assert result.text == "fallback answer"

    def test_force_tier_skips_router(self):
        import core

        events = [result_msg("sess-5")]
        with patch("core.query", return_value=_fake_query_stream(events)), \
             patch("core.choose_tier", new=AsyncMock(return_value="balanced")) as mock_choose:
            result = asyncio.run(core.run_turn("hi", force_tier="deep"))

        mock_choose.assert_not_called()
        assert result.tier == "deep"
        assert result.model == core.TIERS["deep"].model


class TestClassifyWithModel:
    def test_parses_tier_from_response(self):
        import router

        events = [assistant_msg([TextBlock(text="deep")])]
        with patch("router.query", return_value=_fake_query_stream(events)):
            tier = asyncio.run(router.classify_with_model("some ambiguous prompt"))
        assert tier == "deep"

    def test_falls_back_to_default_on_unparseable_response(self):
        import router
        from config import DEFAULT_TIER

        events = [assistant_msg([TextBlock(text="I refuse to answer")])]
        with patch("router.query", return_value=_fake_query_stream(events)):
            tier = asyncio.run(router.classify_with_model("some prompt"))
        assert tier == DEFAULT_TIER

    def test_falls_back_to_default_on_exception(self):
        import router
        from config import DEFAULT_TIER

        async def _raise(*a, **k):
            raise RuntimeError("SDK CLI crashed")
            yield  # pragma: no cover - make this an async generator

        with patch("router.query", side_effect=lambda **k: _raise()):
            tier = asyncio.run(router.classify_with_model("some prompt"))
        assert tier == DEFAULT_TIER

    def test_choose_tier_uses_heuristic_first_without_calling_model(self):
        import router

        with patch("router.classify_with_model", new=AsyncMock()) as mock_classify:
            tier = asyncio.run(router.choose_tier("What is 2+2?"))
        assert tier == "fast"
        mock_classify.assert_not_called()

    def test_choose_tier_falls_back_to_model_when_heuristic_unsure(self):
        import router

        with patch("router.classify_with_model", new=AsyncMock(return_value="balanced")) as mock_classify:
            tier = asyncio.run(router.choose_tier("Summarize this document for me"))
        assert tier == "balanced"
        mock_classify.assert_called_once()
