from pathlib import Path

import pytest

from src.ingestion.loader import chunk_document, load_documents

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_chunk_document_basic():
    """A fully controlled string: verify chunk size, overlap, and coverage."""
    text = "0123456789" * 30  # 300 chars
    chunks = chunk_document(text, chunk_size=100, overlap=20)

    assert len(chunks) == 4
    assert all(len(c) <= 100 for c in chunks)
    # Consecutive chunks overlap by the requested amount.
    assert chunks[0][-20:] == chunks[1][:20]
    assert chunks[1][-20:] == chunks[2][:20]


def test_chunk_document_empty_text_returns_no_chunks():
    assert chunk_document("   ", chunk_size=100, overlap=20) == []


def test_chunk_document_rejects_overlap_gte_chunk_size():
    with pytest.raises(ValueError):
        chunk_document("some text", chunk_size=100, overlap=100)


def test_load_documents_reads_sample_txt_file():
    results = load_documents(str(FIXTURES_DIR))

    assert len(results) > 0

    # Only sample.txt lives in fixtures/, so every chunk should trace back to it.
    sources = {doc["metadata"]["source"] for doc in results}
    assert sources == {"sample.txt"}

    # chunk_index is sequential starting at 0 for the single source file.
    chunk_indices = [doc["metadata"]["chunk_index"] for doc in results]
    assert chunk_indices == list(range(len(results)))

    # Every chunk has real text content, within the configured chunk size.
    for doc in results:
        assert doc["text"].strip() != ""
        assert len(doc["text"]) <= 1000


def test_load_documents_raises_on_missing_dir():
    with pytest.raises(FileNotFoundError):
        load_documents(str(FIXTURES_DIR / "does_not_exist"))
