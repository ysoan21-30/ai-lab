# Multi-Model Agent (Data Science edition)

A Python agent built on the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/), tuned as a data-science assistant:

- **Routes each request to a model tier** (`fast` / `balanced` / `deep`) based on how complex the task looks, so cheap requests use a cheap model and hard ones use your strongest model.
- **Data science tools**: `load_dataset` profiles a CSV/TSV/Parquet/Excel/JSON file (shape, dtypes, nulls, duplicates, summary stats, top categorical values) and `python_exec` runs sandboxed pandas/numpy/matplotlib/scikit-learn/scipy code for EDA, feature engineering, and plotting.
- **Web-scraping-to-RAG-docs**: `scrape_page` (one URL) and `crawl_site` (bounded same-domain crawl) pull in web pages, chunk and embed them with Voyage AI, and store them in a local vector DB. `retrieve_docs` then lets the agent semantically search everything it's ingested — handy for pulling a library's docs or a paper into context before answering.
- **General-purpose starter tools too**: a calculator, sandboxed file read/write, plain web search, and a placeholder for your own internal API.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then edit .env — add ANTHROPIC_API_KEY and (for RAG) VOYAGE_API_KEY
```

`VOYAGE_API_KEY` is only needed for the RAG tools (`scrape_page`, `crawl_site`, `retrieve_docs`) — get a free key at [dash.voyageai.com](https://dash.voyageai.com/). Everything else works without it.

## Run

Three ways to use it, all built on the same `core.run_turn()`:

```bash
# One-shot (scripting / piping)
python agent.py "What is 128 * 47?"

# Interactive terminal REPL — streaming output, colors, conversation memory,
# slash commands (/tier, /auto, /clear, /history, /help, /exit)
python cli.py

# Browser chat UI — dataset upload, inline plots, RAG sources panel, cost tracker
streamlit run web_ui.py
```

`web_ui.py` is the recommended interface for day-to-day data-science work. It adds, on top of
the plain chat:

- **Dataset upload** — drag a csv/tsv/xlsx/parquet/json file into the sidebar; it saves into
  `./workspace` and offers a one-click "Profile it" button that sends a ready-made EDA prompt.
- **Inline plots** — when `python_exec` calls `plt.savefig(...)`, the image shows up directly in
  the chat message (no need to go find the file yourself).
- **RAG sources panel** — lists everything scraped/crawled into the local doc store, with a
  per-source delete button and a clear-all button. Everything shown here lives only in the local
  Chroma DB on disk (`./rag_store`) — nothing is uploaded anywhere by this panel.

`cli.py` is the lighter-weight terminal alternative. Example session:

```
> What is 128 * 47?
Agent 128 × 47 = 6,016
fast · claude-haiku-4-5 · $0.0188

> /tier deep
Forcing tier: deep

> Design a caching strategy for a high-traffic API
Agent ...(streams live)...
deep · claude-opus-4-1 · $0.0489
```

## Project layout

```
config.py         Model tier definitions + RAG/crawl/exec settings
router.py         Decides which tier handles a given prompt (heuristic + model classifier)
core.py           Shared turn-runner: streams a response, handles session resume, used by all 3 UIs
rag.py            Chunking + Voyage embedding + local Chroma vector store (used by the RAG tools)
agent.py          One-shot CLI (no interactivity) — good for scripts/pipes
cli.py            Interactive rich-terminal REPL with streaming + slash commands
web_ui.py         Streamlit browser chat UI
tools/
  data_science.py Dataset profiler (load_dataset) + sandboxed code exec (python_exec)
  scraping.py     scrape_page (single URL) + crawl_site (bounded same-domain crawl) -> ingests into rag.py
  rag_tools.py    retrieve_docs (semantic search) + list_rag_sources (what's been ingested)
  calculator.py   Safe arithmetic tool
  files.py        Sandboxed read_file / write_file (confined to ./workspace)
  web_search.py   No-API-key DuckDuckGo search (swap for Tavily/Brave/SerpAPI in production)
  custom_api.py   Placeholder — copy this pattern to call your own internal API
  __init__.py     Registers all tools into one MCP server exposed to the agent
```

## How the model routing works

`router.py` first checks a few cheap heuristics (prompt length, keyword signals for
"simple lookup" vs. "architecture/strategy/debugging"). If the heuristic is unsure,
it falls back to asking the `fast` tier model to classify the request in one word.
This keeps routing overhead low while still catching non-obvious cases.

Tune the tiers in `config.py`:

```python
TIERS = {
    "fast":     ModelTier(model="claude-haiku-4-5", ...),
    "balanced": ModelTier(model="claude-sonnet-4-5", ...),
    "deep":     ModelTier(model="claude-opus-4-1", ...),
}
```

You can also force a tier for a given call: `run_turn(prompt, force_tier="deep")` (or `/tier deep` in `cli.py`, or the sidebar in the web UI).

## Adding a new tool

1. Create a new file in `tools/` (or add to an existing one) with an `async def` handler
   decorated with `@tool(name, description, input_schema)`.
2. Return `{"content": [{"type": "text", "text": "..."}]}` (add `"is_error": True` on failure).
3. Import it in `tools/__init__.py` and add it to `ALL_TOOLS`.

That's it — it's automatically registered on the MCP server and added to `ALLOWED_TOOL_NAMES`,
so the agent can call it immediately.

## Adding a new model / provider

This project uses Claude models exclusively via the Agent SDK. If you want to route to a
*different provider* (OpenAI, Gemini, etc.) as one of the tiers, the cleanest approach is to
add a branch in `core.py`'s `run_turn()` that calls that provider's SDK directly when
`tier.name == "external"`, bypassing the Claude Agent SDK's `query()` for that branch — the
tools you've defined here won't automatically work with other providers' tool-calling formats,
so you'd need to adapt the schemas per provider.

## Data science workflow

Typical session:

```
> Load employees.csv and give me a quick EDA summary, then suggest 2 useful engineered features
```

The agent will call `load_dataset` first (profile: nulls, dtypes, duplicates, summary stats),
then `python_exec` to actually compute things and save any plots, flagging data-quality issues
(missing values, class imbalance, leakage risk) along the way — see the system prompt in
`core.py` for the exact persona/instructions. Point it at files under `./workspace/`.

## Building a RAG doc set from the web

```
> Scrape https://pandas.pydata.org/docs/user_guide/merging.html and summarize the key merge types
> Crawl https://scikit-learn.org/stable/modules/preprocessing.html with max_depth 1 and ingest it
> What does the scikit-learn preprocessing guide say about scaling sparse data?
```

- `scrape_page` ingests exactly one URL.
- `crawl_site` does a bounded breadth-first crawl (same domain only, capped by `CRAWL_MAX_PAGES` /
  `CRAWL_MAX_DEPTH` in `.env` — defaults 20 pages / depth 2) and ingests every page it visits.
- Both chunk the extracted text (`RAG_CHUNK_SIZE`/`RAG_CHUNK_OVERLAP`), embed with Voyage AI
  (`VOYAGE_EMBED_MODEL`, default `voyage-3.5`), and upsert into a local Chroma store at
  `RAG_DB_DIR` (default `./rag_store`) — it persists across runs.
- `retrieve_docs` does the semantic search; `list_rag_sources` shows what's in the store.

## Notes

- `web_search` uses an unauthenticated DuckDuckGo HTML scrape so the project runs out of the
  box with no extra API keys. It's rate-limitable and not meant for heavy production use —
  swap in Tavily, Brave Search, or SerpAPI when you're ready.
- `scrape_page` / `crawl_site` extract text with a general-purpose HTML cleaner (strips nav/
  footer/scripts). Heavily JS-rendered pages need a real browser to render — out of scope here.
- `crawl_site` only follows links on the same domain as the start URL, and hard-caps at
  3× `CRAWL_MAX_PAGES` regardless of what's passed in, so it can't run away on a huge site.
- `python_exec` runs real code in a subprocess confined to the workspace directory, with a
  timeout (`DS_EXEC_TIMEOUT_SECONDS`) — it is **not** a hard security sandbox (the subprocess
  still has normal filesystem/network access within its own permissions). Don't expose this
  agent to untrusted input if you wire it up to run arbitrary user-submitted code.
- `read_file` / `write_file` are sandboxed to `./workspace` (configurable via
  `AGENT_WORKSPACE_DIR`) and reject any path that tries to escape that directory.
- `custom_api.py` is intentionally a stub — replace its body with a real HTTP call to your
  own service.
