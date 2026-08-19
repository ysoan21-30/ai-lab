"""
Local RAG store: chunk scraped text, embed with Voyage AI, persist in a
local ChromaDB collection, and retrieve by semantic similarity.

This module is deliberately provider-agnostic on the vector-DB side (plain
Chroma with precomputed embeddings) so swapping Voyage for another embedder
later only touches `embed_texts()` / `embed_query()`.
"""

import hashlib
import re
from dataclasses import dataclass

import chromadb

from config import (
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_COLLECTION,
    RAG_DB_DIR,
    VOYAGE_API_KEY,
    VOYAGE_EMBED_MODEL,
)

_client = None
_voyage_client = None


def _get_chroma_collection():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=RAG_DB_DIR)
    return _client.get_or_create_collection(RAG_COLLECTION)


def _get_voyage_client():
    global _voyage_client
    if _voyage_client is None:
        if not VOYAGE_API_KEY:
            raise RuntimeError(
                "VOYAGE_API_KEY is not set. Add it to your .env file — get a key at "
                "https://dash.voyageai.com/"
            )
        import voyageai

        _voyage_client = voyageai.AsyncClient(api_key=VOYAGE_API_KEY)
    return _voyage_client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    client = _get_voyage_client()
    result = await client.embed(texts, model=VOYAGE_EMBED_MODEL, input_type="document")
    return result.embeddings


async def embed_query(text: str) -> list[float]:
    client = _get_voyage_client()
    result = await client.embed([text], model=VOYAGE_EMBED_MODEL, input_type="query")
    return result.embeddings[0]


def chunk_text(text: str, chunk_size: int = RAG_CHUNK_SIZE, overlap: int = RAG_CHUNK_OVERLAP) -> list[str]:
    """Simple fixed-size character chunker with overlap, splitting on
    paragraph/sentence boundaries where possible so chunks don't cut mid-word
    more than necessary."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # Try to break at a paragraph or sentence boundary near `end`.
            boundary = text.rfind("\n\n", start, end)
            if boundary == -1 or boundary <= start:
                boundary = text.rfind(". ", start, end)
            if boundary != -1 and boundary > start:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        next_start = end - overlap
        start = next_start if next_start > start else end
    return chunks


def _chunk_id(source: str, index: int) -> str:
    digest = hashlib.sha256(f"{source}::{index}".encode()).hexdigest()[:16]
    return f"{digest}-{index}"


async def ingest_document(source: str, title: str, text: str) -> int:
    """Chunk, embed, and upsert a document's text into the vector store.
    Returns the number of chunks stored."""
    chunks = chunk_text(text)
    if not chunks:
        return 0

    embeddings = await embed_texts(chunks)
    collection = _get_chroma_collection()

    ids = [_chunk_id(source, i) for i in range(len(chunks))]
    metadatas = [{"source": source, "title": title, "chunk_index": i} for i in range(len(chunks))]

    collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    return len(chunks)


@dataclass
class RetrievedChunk:
    text: str
    source: str
    title: str
    distance: float


async def retrieve(query: str, top_k: int = 5) -> list[RetrievedChunk]:
    collection = _get_chroma_collection()
    if collection.count() == 0:
        return []

    query_embedding = await embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
    )

    out = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        out.append(
            RetrievedChunk(
                text=doc,
                source=meta.get("source", "unknown"),
                title=meta.get("title", ""),
                distance=dist,
            )
        )
    return out


def list_sources() -> list[dict]:
    """Return distinct sources currently ingested, with chunk counts."""
    collection = _get_chroma_collection()
    if collection.count() == 0:
        return []
    data = collection.get(include=["metadatas"])
    counts: dict[str, dict] = {}
    for meta in data.get("metadatas", []):
        source = meta.get("source", "unknown")
        if source not in counts:
            counts[source] = {"source": source, "title": meta.get("title", ""), "chunks": 0}
        counts[source]["chunks"] += 1
    return list(counts.values())


def clear_store() -> None:
    """Wipe every chunk from the local RAG collection. Everything stays on
    disk (RAG_DB_DIR) — nothing is sent anywhere — this just empties it."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=RAG_DB_DIR)
    _client.delete_collection(RAG_COLLECTION)
    _client.get_or_create_collection(RAG_COLLECTION)


def remove_source(source: str) -> int:
    """Delete all chunks belonging to one source URL. Returns how many were
    removed (0 if the source wasn't found)."""
    collection = _get_chroma_collection()
    if collection.count() == 0:
        return 0
    matches = collection.get(where={"source": source}, include=[])
    ids = matches.get("ids", [])
    if ids:
        collection.delete(ids=ids)
    return len(ids)
