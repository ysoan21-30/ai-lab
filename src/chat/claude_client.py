"""Thin wrapper around the Anthropic Claude API for the RAG chat loop.

TODO: implement retrieval-augmented prompt construction and response
generation (with streaming) once ingestion/retrieval are in place.
"""

import anthropic

from src.config import settings


def get_client() -> anthropic.Anthropic:
    """Return an Anthropic client (reads ANTHROPIC_API_KEY from env)."""
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def answer_question(question: str, context_chunks: list[str]) -> str:
    """Generate a fraud-analysis answer grounded in retrieved context chunks."""
    raise NotImplementedError
