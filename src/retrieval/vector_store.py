"""ChromaDB-backed vector store for fraud knowledge base chunks.

Embeddings come from the Voyage AI API (Anthropic's recommended embedding
provider) rather than Chroma's default local sentence-transformers model —
no model weights are downloaded and no local inference runs.
"""

import time
import uuid
from collections.abc import Callable

import chromadb
import voyageai

from src.config import settings

# Voyage AI's free tier caps requests at 3/minute and 10,000 tokens/minute.
# Chunks are ~1000 characters (~250 tokens) by default, so a batch of 10
# keeps each request to ~2500 tokens — well under the token cap even if
# all 3 requests land in the same minute — while the delay between batches
# keeps request frequency under the 3/minute cap.
EMBED_BATCH_SIZE = 10
EMBED_REQUEST_DELAY_SECONDS = 21  # a little over 60s / 3 requests, for margin


class VoyageEmbeddingFunction:
    """Chroma-compatible embedding function backed by the Voyage AI API.

    Always embeds with input_type="document" — this is the function Chroma
    calls internally when documents are added to the collection. Queries are
    embedded separately (see `query()` below) with input_type="query" for
    Voyage's asymmetric retrieval optimization.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._client = voyageai.Client(api_key=api_key or settings.voyage_api_key)
        self._model = model or settings.voyage_embedding_model

    def name(self) -> str:
        return f"voyage:{self._model}"

    def __call__(self, input: list[str]) -> list[list[float]]:
        result = self._client.embed(input, model=self._model, input_type="document")
        return result.embeddings

    def embed_query(self, input: list[str]) -> list[list[float]]:
        # `query()` below calls Voyage directly with input_type="query"
        # rather than relying on Chroma to invoke this hook, but it's
        # implemented for correctness in case this collection is ever
        # queried the standard Chroma way (`collection.query(query_texts=...)`).
        result = self._client.embed(input, model=self._model, input_type="query")
        return result.embeddings

    def get_config(self) -> dict:
        return {"model": self._model}

    @staticmethod
    def build_from_config(config: dict) -> "VoyageEmbeddingFunction":
        return VoyageEmbeddingFunction(model=config.get("model"))


_collection = None
_voyage_client = None


def _get_voyage_client() -> voyageai.Client:
    global _voyage_client
    if _voyage_client is None:
        _voyage_client = voyageai.Client(api_key=settings.voyage_api_key)
    return _voyage_client


def get_collection():
    """Return (creating if needed) the persistent ChromaDB collection, wired
    up to the Voyage AI embedding function."""
    global _collection
    if _collection is not None:
        return _collection

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    _collection = client.get_or_create_collection(
        name=settings.chroma_collection_name,
        embedding_function=VoyageEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def _make_id(chunk: dict) -> str:
    """Derive a stable ID from a chunk's source/chunk_index metadata so
    re-ingesting the same file updates its chunks instead of duplicating
    them. Falls back to a random UUID if that metadata isn't present."""
    metadata = chunk["metadata"]
    source = metadata.get("source")
    chunk_index = metadata.get("chunk_index")
    if source is not None and chunk_index is not None:
        return f"{source}::{chunk_index}"
    return str(uuid.uuid4())


def add_documents(
    chunks: list[dict],
    collection=None,
    voyage_client=None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[str]:
    """Embed (via Voyage AI, input_type="document") and upsert `chunks` into
    the collection.

    `chunks` is the list of {"text": ..., "metadata": {...}} dicts produced
    by `src.ingestion.loader.load_documents`. To respect Voyage's free-tier
    rate limits, chunks are embedded in small batches (`EMBED_BATCH_SIZE`)
    with a delay (`EMBED_REQUEST_DELAY_SECONDS`) between Voyage API calls —
    embeddings are computed here and passed to `collection.upsert()`
    explicitly, rather than relying on the collection's registered
    embedding_function to embed everything in one uncontrolled call.

    If given, `progress_callback(chunks_done, total_chunks)` is called after
    each batch completes, so a caller (e.g. the Streamlit UI) can show
    ingestion progress. Returns the list of IDs that were upserted.
    """
    if not chunks:
        return []

    collection = collection if collection is not None else get_collection()
    voyage_client = voyage_client if voyage_client is not None else _get_voyage_client()

    ids = [_make_id(chunk) for chunk in chunks]
    documents = [chunk["text"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]

    total = len(chunks)
    batch_starts = list(range(0, total, EMBED_BATCH_SIZE))

    for batch_num, start in enumerate(batch_starts):
        end = min(start + EMBED_BATCH_SIZE, total)

        batch_embeddings = voyage_client.embed(
            documents[start:end],
            model=settings.voyage_embedding_model,
            input_type="document",
        ).embeddings

        collection.upsert(
            documents=documents[start:end],
            metadatas=metadatas[start:end],
            ids=ids[start:end],
            embeddings=batch_embeddings,
        )

        if progress_callback is not None:
            progress_callback(end, total)

        is_last_batch = batch_num == len(batch_starts) - 1
        if not is_last_batch:
            time.sleep(EMBED_REQUEST_DELAY_SECONDS)

    return ids


def query(query_text: str, k: int = 5, collection=None, voyage_client=None) -> list[dict]:
    """Return the top-`k` chunks most relevant to `query_text`.

    The query is embedded directly via Voyage AI with input_type="query" —
    bypassing the collection's registered embedding_function, which always
    embeds with input_type="document" — for the asymmetric query/document
    embedding Voyage recommends for retrieval quality.

    Returns a list of {"text", "metadata", "score"} dicts, ranked most
    relevant first. `score` is cosine similarity (1 - cosine distance).
    """
    if not query_text or not query_text.strip():
        return []

    collection = collection if collection is not None else get_collection()
    voyage_client = voyage_client if voyage_client is not None else _get_voyage_client()

    embedding = voyage_client.embed(
        [query_text], model=settings.voyage_embedding_model, input_type="query"
    ).embeddings[0]

    results = collection.query(query_embeddings=[embedding], n_results=k)

    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    return [
        {
            "text": text,
            "metadata": metadata,
            "score": (1 - distance) if distance is not None else None,
        }
        for text, metadata, distance in zip(documents, metadatas, distances)
    ]
