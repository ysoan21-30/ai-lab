"""
Web scraping tools that feed the local RAG doc store.

- scrape_page: fetch one URL, extract clean text, ingest it as a document.
- crawl_site: bounded breadth-first crawl of a site (same domain only,
  capped depth/page count) that ingests every page it visits.

Both use a simple HTML->text extraction (strip script/style/nav/footer,
collapse whitespace) via BeautifulSoup. This is a general-purpose extractor,
not tuned for any one site's markup — expect some noise on heavily
JS-rendered pages (those need a real browser to render, which is out of
scope for this lightweight tool).
"""

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from claude_agent_sdk import tool

from config import CRAWL_MAX_DEPTH, CRAWL_MAX_PAGES
from rag import ingest_document

HEADERS = {"User-Agent": "Mozilla/5.0 (multi-model-agent RAG ingester)"}
NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]


def _extract_text(html: str) -> tuple[str, str]:
    """Returns (title, clean_text)."""
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    for tag in soup(NOISE_TAGS):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return title, text.strip()


def _extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc
    links = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].split("#")[0])
        parsed = urlparse(href)
        if parsed.scheme in ("http", "https") and parsed.netloc == base_domain:
            links.add(href)
    return list(links)


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, headers=HEADERS, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return None
        return resp.text
    except httpx.HTTPError:
        return None


@tool(
    "scrape_page",
    (
        "Fetch a single web page, extract its main readable text, and add it to the "
        "local RAG document store so it can be searched later with retrieve_docs. "
        "Use this for one specific URL (e.g. a docs page, an article, a blog post)."
    ),
    {"url": str},
)
async def scrape_page(args: dict[str, Any]) -> dict[str, Any]:
    url = args["url"]

    async with httpx.AsyncClient() as client:
        html = await _fetch(client, url)

    if html is None:
        return {
            "content": [{"type": "text", "text": f"Could not fetch or parse: {url}"}],
            "is_error": True,
        }

    title, text = _extract_text(html)
    if not text:
        return {
            "content": [{"type": "text", "text": f"No readable text extracted from {url}"}],
            "is_error": True,
        }

    num_chunks = await ingest_document(source=url, title=title, text=text)
    preview = text[:400] + ("..." if len(text) > 400 else "")

    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Ingested '{title or url}' — {len(text)} chars, {num_chunks} chunk(s) added "
                    f"to the doc store.\n\nPreview:\n{preview}"
                ),
            }
        ]
    }


@tool(
    "crawl_site",
    (
        "Crawl a website starting from a URL, following same-domain links up to a page/depth "
        f"limit (defaults: {CRAWL_MAX_PAGES} pages, depth {CRAWL_MAX_DEPTH}), and ingest every "
        "page's text into the RAG document store. Use this to build a fuller knowledge base from "
        "a documentation site, rather than one page at a time."
    ),
    {"start_url": str, "max_pages": int, "max_depth": int},
)
async def crawl_site(args: dict[str, Any]) -> dict[str, Any]:
    start_url = args["start_url"]
    max_pages = args.get("max_pages") or CRAWL_MAX_PAGES
    max_depth = args.get("max_depth") if args.get("max_depth") is not None else CRAWL_MAX_DEPTH
    max_pages = min(max_pages, CRAWL_MAX_PAGES * 3)  # hard ceiling so the tool can't run away

    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(start_url, 0)]
    ingested: list[str] = []
    skipped: list[str] = []

    async with httpx.AsyncClient() as client:
        while queue and len(visited) < max_pages:
            url, depth = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            html = await _fetch(client, url)
            if html is None:
                skipped.append(url)
                continue

            title, text = _extract_text(html)
            if text:
                num_chunks = await ingest_document(source=url, title=title, text=text)
                ingested.append(f"{url} ({num_chunks} chunks)")

            if depth < max_depth:
                for link in _extract_links(html, url):
                    if link not in visited:
                        queue.append((link, depth + 1))

    summary_lines = [
        f"Crawled {len(visited)} page(s) from {start_url} (max_pages={max_pages}, max_depth={max_depth}).",
        f"Ingested {len(ingested)} page(s):",
    ]
    summary_lines += [f"  - {line}" for line in ingested[:25]]
    if len(ingested) > 25:
        summary_lines.append(f"  ... and {len(ingested) - 25} more")
    if skipped:
        summary_lines.append(f"Skipped {len(skipped)} unfetchable/non-HTML page(s).")

    return {"content": [{"type": "text", "text": "\n".join(summary_lines)}]}
