"""Tests for src/chat/claude_client.py.

Fast tests mock both the Anthropic client and vector_store.query — no
network calls. The single @pytest.mark.integration test hits the real
Claude API (with retrieval mocked, since that's covered separately in
test_vector_store.py's own integration test) and is excluded by default;
run it explicitly with `pytest -m integration` (requires a real
ANTHROPIC_API_KEY in the environment).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.chat.claude_client import SYSTEM_PROMPT, answer_question
from src.config import settings

SAMPLE_CHUNKS = [
    {
        "text": "Case notes: suspicious wire transfer flagged for manual review.",
        "metadata": {"source": "wire_cases.txt", "chunk_index": 0},
        "score": 0.92,
    },
    {
        "text": "Report: customer reported a phishing email requesting login credentials.",
        "metadata": {"source": "phishing_cases.txt", "chunk_index": 0},
        "score": 0.81,
    },
]


def _fake_response(text="Wire transfers are flagged for manual review. [1]", stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
    )


def _fake_client(response=None):
    client = MagicMock()
    client.messages.create.return_value = response or _fake_response()
    return client


def test_answer_question_queries_vector_store_with_question_and_k():
    query_fn = MagicMock(return_value=SAMPLE_CHUNKS)
    client = _fake_client()

    answer_question("What happened with wire transfers?", k=3, client=client, query_fn=query_fn)

    query_fn.assert_called_once_with("What happened with wire transfers?", k=3)


def test_answer_question_sends_context_and_question_in_user_message():
    query_fn = MagicMock(return_value=SAMPLE_CHUNKS)
    client = _fake_client()

    answer_question("What happened with wire transfers?", client=client, query_fn=query_fn)

    kwargs = client.messages.create.call_args.kwargs
    user_message = kwargs["messages"][0]["content"]
    assert "What happened with wire transfers?" in user_message
    assert "suspicious wire transfer flagged" in user_message
    assert "wire_cases.txt" in user_message
    assert "phishing_cases.txt" in user_message


def test_answer_question_uses_configured_model():
    query_fn = MagicMock(return_value=SAMPLE_CHUNKS)
    client = _fake_client()

    answer_question("q", client=client, query_fn=query_fn)

    assert client.messages.create.call_args.kwargs["model"] == settings.anthropic_model


def test_answer_question_caches_the_identical_system_prompt_across_calls():
    query_fn = MagicMock(return_value=SAMPLE_CHUNKS)
    client = _fake_client()

    answer_question("First question", client=client, query_fn=query_fn)
    answer_question("A completely different question", client=client, query_fn=query_fn)

    first_system = client.messages.create.call_args_list[0].kwargs["system"]
    second_system = client.messages.create.call_args_list[1].kwargs["system"]
    expected = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]

    assert first_system == second_system == expected


def test_answer_question_returns_answer_text_and_source_metadata():
    query_fn = MagicMock(return_value=SAMPLE_CHUNKS)
    client = _fake_client(_fake_response(text="Wire transfers were flagged. [1]"))

    result = answer_question("q", client=client, query_fn=query_fn)

    assert result == {
        "answer": "Wire transfers were flagged. [1]",
        "sources": [chunk["metadata"] for chunk in SAMPLE_CHUNKS],
    }


def test_answer_question_handles_refusal_without_crashing():
    query_fn = MagicMock(return_value=SAMPLE_CHUNKS)
    client = _fake_client(_fake_response(text="", stop_reason="refusal"))

    result = answer_question("q", client=client, query_fn=query_fn)

    assert result["sources"] == []
    assert result["answer"]  # non-empty fallback message, not a silent empty string


def test_answer_question_handles_no_retrieved_chunks():
    query_fn = MagicMock(return_value=[])
    client = _fake_client()

    result = answer_question("q", client=client, query_fn=query_fn)

    assert result["sources"] == []
    user_message = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "No relevant context" in user_message


@pytest.mark.integration
@pytest.mark.skipif(not settings.anthropic_api_key, reason="requires a real ANTHROPIC_API_KEY")
def test_answer_question_with_real_anthropic_api():
    """End-to-end smoke test against the real Claude API.

    Retrieval is mocked (covered separately by test_vector_store.py's own
    integration test) so this test isolates the Claude call itself.
    """
    query_fn = MagicMock(return_value=SAMPLE_CHUNKS)

    result = answer_question(
        "What kind of fraud case involved a wire transfer?", k=2, query_fn=query_fn
    )

    assert isinstance(result["answer"], str) and result["answer"].strip()
    assert result["sources"] == [chunk["metadata"] for chunk in SAMPLE_CHUNKS]
