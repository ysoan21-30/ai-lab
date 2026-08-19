"""Tests for the pure chunk_text() logic in rag.py (no Voyage/Chroma calls)."""
from rag import chunk_text


class TestChunkText:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("Hello world.", chunk_size=1500, overlap=200)
        assert chunks == ["Hello world."]

    def test_empty_text_no_chunks(self):
        assert chunk_text("", chunk_size=1500, overlap=200) == []

    def test_whitespace_only_no_chunks(self):
        assert chunk_text("   \n\n\n  ", chunk_size=1500, overlap=200) == []

    def test_long_text_splits_into_multiple_chunks(self):
        text = ("This is a sentence. " * 200).strip()
        chunks = chunk_text(text, chunk_size=300, overlap=50)
        assert len(chunks) > 1
        for c in chunks:
            # allow a little slack since we search for a boundary near chunk_size
            assert len(c) <= 300 + 50

    def test_chunks_cover_all_content_no_loss(self):
        # Every unique word present in the source should show up somewhere in the chunks
        # (overlap means some duplication, but nothing should vanish).
        text = " ".join(f"word{i}" for i in range(500))
        chunks = chunk_text(text, chunk_size=200, overlap=20)
        joined = " ".join(chunks)
        for i in (0, 250, 499):
            assert f"word{i}" in joined

    def test_excess_blank_lines_collapsed(self):
        text = "para one\n\n\n\n\npara two"
        chunks = chunk_text(text, chunk_size=1500, overlap=200)
        assert chunks == ["para one\n\npara two"]

    def test_no_infinite_loop_on_small_overlap_edge_case(self):
        # Regression guard: if overlap >= chunk_size the naive `start = end - overlap`
        # could stall or loop forever. Should terminate quickly regardless.
        text = "x" * 5000
        chunks = chunk_text(text, chunk_size=100, overlap=100)
        assert len(chunks) > 0
        assert sum(len(c) for c in chunks) >= len(text)  # no data lost even with overlap

    def test_overlap_larger_than_chunk_size_terminates(self):
        text = "y" * 2000
        chunks = chunk_text(text, chunk_size=100, overlap=500)
        assert len(chunks) > 0
