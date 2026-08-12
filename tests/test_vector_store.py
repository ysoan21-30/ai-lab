"""Tests for src/retrieval/vector_store.py.

Fast tests use an in-memory Chroma client (never touches data/chroma_db)
plus fake embedding functions/clients — no network calls. The single
@pytest.mark.integration test hits the real Voyage AI API and is excluded
by default; run it explicitly with `pytest -m integration` (requires a real
VOYAGE_API_KEY in the environment).
"""

import uuid
from types import SimpleNamespace

import chromadb
import pytest

from src.config import settings
from src.retrieval.vector_store import VoyageEmbeddingFunction, add_documents, query

SAMPLE_CHUNKS = [
    {
        "text": "Case notes: suspicious wire transfer flagged for manual review.",
        "metadata": {"source": "wire_cases.txt", "chunk_index": 0},
    },
    {
        "text": "Report: customer reported a phishing email requesting login credentials.",
        "metadata": {"source": "phishing_cases.txt", "chunk_index": 0},
    },
]


def _keyword_vector(text: str) -> list[float]:
    """Deterministic 2-D stand-in embedding: [wire-transfer-ness, phishing-ness]."""
    lowered = text.lower()
    return [
        1.0 if "wire transfer" in lowered else 0.0,
        1.0 if "phishing" in lowered else 0.0,
    ]


class FakeEmbeddingFunction:
    """Chroma-compatible embedding function used for fast, offline tests."""

    def name(self) -> str:
        return "fake"

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [_keyword_vector(t) for t in input]

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "FakeEmbeddingFunction":
        return FakeEmbeddingFunction()


class FakeVoyageClient:
    """Stand-in for voyageai.Client — mirrors the real .embed() response shape."""

    def __init__(self):
        self.calls = []

    def embed(self, texts, model=None, input_type=None):
        self.calls.append({"texts": list(texts), "model": model, "input_type": input_type})
        return SimpleNamespace(embeddings=[_keyword_vector(t) for t in texts])


@pytest.fixture
def in_memory_collection():
    """A fresh, non-persisted Chroma collection wired to the fake embedding fn.

    chromadb.Client() shares its in-memory backend across Client() instances
    within a process (keyed by tenant/database, not by object), so each
    collection gets a unique name to avoid colliding with other tests.
    """
    client = chromadb.Client()  # ephemeral, in-memory — never touches data/chroma_db
    return client.create_collection(
        name=f"test_collection_{uuid.uuid4().hex}",
        embedding_function=FakeEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def test_add_documents_generates_stable_ids_from_metadata(in_memory_collection):
    ids = add_documents(SAMPLE_CHUNKS, collection=in_memory_collection)

    assert ids == ["wire_cases.txt::0", "phishing_cases.txt::0"]
    assert in_memory_collection.count() == 2


def test_add_documents_reingest_upserts_instead_of_duplicating(in_memory_collection):
    add_documents(SAMPLE_CHUNKS, collection=in_memory_collection)
    add_documents(SAMPLE_CHUNKS, collection=in_memory_collection)  # re-ingest same file

    # Same source + chunk_index -> same ID -> upsert, not duplicate rows.
    assert in_memory_collection.count() == 2


def test_add_documents_empty_list_is_a_noop(in_memory_collection):
    assert add_documents([], collection=in_memory_collection) == []
    assert in_memory_collection.count() == 0


def test_query_embeds_query_text_with_input_type_query(in_memory_collection):
    add_documents(SAMPLE_CHUNKS, collection=in_memory_collection)
    fake_client = FakeVoyageClient()

    query(
        "Tell me about wire transfers",
        k=1,
        collection=in_memory_collection,
        voyage_client=fake_client,
    )

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["input_type"] == "query"


def test_query_returns_top_k_ranked_chunks_with_text_metadata_score(in_memory_collection):
    add_documents(SAMPLE_CHUNKS, collection=in_memory_collection)
    fake_client = FakeVoyageClient()

    results = query(
        "Tell me about wire transfers",
        k=1,
        collection=in_memory_collection,
        voyage_client=fake_client,
    )

    assert len(results) == 1
    top = results[0]
    assert set(top.keys()) == {"text", "metadata", "score"}
    assert "wire transfer" in top["text"].lower()
    assert top["metadata"]["source"] == "wire_cases.txt"
    assert top["score"] == pytest.approx(1.0)


def test_query_empty_text_returns_no_results(in_memory_collection):
    add_documents(SAMPLE_CHUNKS, collection=in_memory_collection)
    assert query("   ", collection=in_memory_collection, voyage_client=FakeVoyageClient()) == []


@pytest.mark.integration
@pytest.mark.skipif(not settings.voyage_api_key, reason="requires a real VOYAGE_API_KEY")
def test_add_and_query_with_real_voyage_api():
    """End-to-end smoke test against the real Voyage AI API.

    Uses an ephemeral in-memory Chroma collection (never touches
    data/chroma_db), but makes real network calls to Voyage.
    """
    client = chromadb.Client()
    collection = client.create_collection(
        name=f"integration_test_collection_{uuid.uuid4().hex}",
        embedding_function=VoyageEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )

    add_documents(SAMPLE_CHUNKS, collection=collection)
    results = query("wire transfer fraud", k=1, collection=collection)

    assert len(results) == 1
    assert results[0]["metadata"]["source"] == "wire_cases.txt"
    assert isinstance(results[0]["score"], float)
