"""Tools that let the agent search and inspect the local RAG doc store built
by scrape_page / crawl_site (see tools/scraping.py)."""

from typing import Any

from claude_agent_sdk import tool

import rag


@tool(
    "retrieve_docs",
    (
        "Semantically search the local RAG document store (built via scrape_page/crawl_site) "
        "and return the most relevant text chunks with their source URLs. Use this before "
        "answering questions about docs/pages you or the user has scraped, instead of relying "
        "on memory."
    ),
    {"query": str, "top_k": int},
)
async def retrieve_docs(args: dict[str, Any]) -> dict[str, Any]:
    query = args["query"]
    top_k = args.get("top_k") or 5

    try:
        results = await rag.retrieve(query, top_k=top_k)
    except RuntimeError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}

    if not results:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "No documents in the RAG store yet (or no relevant matches). "
                        "Use scrape_page or crawl_site to ingest some pages first."
                    ),
                }
            ]
        }

    lines = [f"Top {len(results)} result(s) for: '{query}'\n"]
    for i, chunk in enumerate(results, 1):
        lines.append(f"[{i}] {chunk.title or chunk.source} ({chunk.source})")
        lines.append(f"    {chunk.text[:500]}{'...' if len(chunk.text) > 500 else ''}")
        lines.append("")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    "list_rag_sources",
    "List every source URL currently ingested into the local RAG document store, with chunk counts.",
    {},
)
async def list_rag_sources(args: dict[str, Any]) -> dict[str, Any]:
    sources = rag.list_sources()
    if not sources:
        return {"content": [{"type": "text", "text": "The RAG store is empty."}]}

    lines = [f"{len(sources)} source(s) in the RAG store:"]
    for s in sources:
        lines.append(f"  - {s['title'] or s['source']} — {s['chunks']} chunk(s) — {s['source']}")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}
