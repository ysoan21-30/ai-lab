"""
Model routing configuration for the multi-model agent.

The idea: not every request deserves your most expensive model. We define
three tiers and a lightweight classifier that picks a tier per request based
on the task's apparent complexity. You can tune the tiers, the classifier
prompt, or replace the classifier with your own heuristic (keyword rules,
token-length thresholds, a small local model, etc).
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelTier:
    name: str
    model: str
    description: str


# Three tiers, cheapest/fastest to most capable/expensive.
# Override via .env if you want different model IDs.
TIERS: dict[str, ModelTier] = {
    "fast": ModelTier(
        name="fast",
        model=os.environ.get("MODEL_TIER_FAST", "claude-haiku-4-5"),
        description="Simple lookups, formatting, short factual answers, tool-only tasks.",
    ),
    "balanced": ModelTier(
        name="balanced",
        model=os.environ.get("MODEL_TIER_BALANCED", "claude-sonnet-4-5"),
        description="General reasoning, multi-step tool use, everyday coding/writing tasks.",
    ),
    "deep": ModelTier(
        name="deep",
        model=os.environ.get("MODEL_TIER_DEEP", "claude-opus-4-1"),
        description="Hard reasoning, ambiguous/high-stakes tasks, long multi-step planning.",
    ),
}

# The model used to *classify* which tier a request needs. Keep this cheap —
# it's an overhead call on every request.
ROUTER_MODEL = TIERS["fast"].model

DEFAULT_TIER = "balanced"

# --- RAG / web-scraping-into-docs settings -----------------------------

# Voyage AI is Anthropic's recommended embedding provider. Get a key at
# https://dash.voyageai.com/ and put it in .env as VOYAGE_API_KEY.
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY")
VOYAGE_EMBED_MODEL = os.environ.get("VOYAGE_EMBED_MODEL", "voyage-3.5")

# Where the local Chroma vector store persists to disk.
RAG_DB_DIR = os.environ.get("RAG_DB_DIR", "./rag_store")
RAG_COLLECTION = os.environ.get("RAG_COLLECTION", "docs")

# Chunking parameters for scraped text before embedding.
RAG_CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "1500"))  # characters
RAG_CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "200"))  # characters

# Crawler guardrails.
CRAWL_MAX_PAGES = int(os.environ.get("CRAWL_MAX_PAGES", "20"))
CRAWL_MAX_DEPTH = int(os.environ.get("CRAWL_MAX_DEPTH", "2"))

# Timeout for the python_exec data-science tool (which shares its sandbox dir
# with read_file/write_file — see AGENT_WORKSPACE_DIR in tools/files.py).
DS_EXEC_TIMEOUT_SECONDS = int(os.environ.get("DS_EXEC_TIMEOUT_SECONDS", "30"))
