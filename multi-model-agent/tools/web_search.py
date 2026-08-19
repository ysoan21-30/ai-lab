"""Web search tool.

Ships with a no-API-key DuckDuckGo HTML search as a working default so the
project runs out of the box. For production use, swap this out for a proper
search API (Tavily, Brave Search, SerpAPI, Bing) — they're more reliable and
less likely to be rate-limited or change their markup.
"""

from typing import Any

import httpx
from claude_agent_sdk import tool

DDG_URL = "https://html.duckduckgo.com/html/"


@tool(
    "web_search",
    "Search the web and return a short list of results (title, snippet, URL) for a query.",
    {"query": str},
)
async def web_search(args: dict[str, Any]) -> dict[str, Any]:
    query = args["query"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                DDG_URL,
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (multi-model-agent)"},
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "content": [{"type": "text", "text": f"Search failed: {exc}"}],
            "is_error": True,
        }

    # Minimal, dependency-free scrape of DuckDuckGo's HTML results.
    import re

    results = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text
    )
    if not results:
        return {"content": [{"type": "text", "text": f"No results found for '{query}'."}]}

    lines = [f"Results for '{query}':"]
    for url, title in results[:5]:
        clean_title = re.sub(r"<[^>]+>", "", title)
        lines.append(f"- {clean_title}\n  {url}")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}
