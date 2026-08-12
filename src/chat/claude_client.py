"""Retrieval-augmented Claude client for fraud-analysis Q&A."""

import anthropic

from src.config import settings
from src.retrieval import vector_store

ANSWER_MAX_TOKENS = 1024

# Static and identical across every call, so it's marked cache_control —
# only the user turn (context + question) varies per request.
SYSTEM_PROMPT = (
    "You are a fraud analysis assistant. Answer the user's question using "
    "ONLY the information given in the context chunks below the question — "
    "never rely on outside knowledge, even if you know the answer.\n\n"
    "If the context does not contain enough information to answer the "
    'question, respond exactly: "I don\'t have enough information to answer '
    'that based on the available documents."\n\n'
    "When you do answer, cite the source document(s) your answer relies on."
)


def get_client() -> anthropic.Anthropic:
    """Return an Anthropic client (reads ANTHROPIC_API_KEY from env)."""
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _format_context(chunks: list[dict]) -> str:
    if not chunks:
        return "(No relevant context was found in the knowledge base.)"
    return "\n\n".join(
        f"[{i}] Source: {chunk['metadata'].get('source', 'unknown')}\n{chunk['text']}"
        for i, chunk in enumerate(chunks, start=1)
    )


def _build_user_message(question: str, chunks: list[dict]) -> str:
    return f"Context:\n{_format_context(chunks)}\n\nQuestion: {question}"


def answer_question(question: str, k: int = 5, client=None, query_fn=None) -> dict:
    """Answer `question` using retrieval-augmented generation.

    1. Retrieves the top-`k` relevant chunks via `vector_store.query`.
    2. Sends Claude a static, prompt-cached system prompt (grounding rules)
       plus a user turn containing the retrieved context and the question.
    3. Returns {"answer": str, "sources": [chunk metadata, ...]}.
    """
    query_fn = query_fn or vector_store.query
    chunks = query_fn(question, k=k)

    client = client or get_client()
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=ANSWER_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": _build_user_message(question, chunks)}],
    )

    if response.stop_reason == "refusal":
        return {"answer": "I'm unable to answer that question.", "sources": []}

    answer_text = next((block.text for block in response.content if block.type == "text"), "")

    return {
        "answer": answer_text,
        "sources": [chunk["metadata"] for chunk in chunks],
    }
