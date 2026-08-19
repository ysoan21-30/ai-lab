"""
Streamlit web chat UI for the multi-model agent.

Run:
    streamlit run web_ui.py

Features:
  - Chat-style interface with conversation memory (session_id resumed each turn)
  - Sidebar: forced model tier, live cost tracker, dataset upload, RAG sources panel
  - Dataset upload: drop a csv/tsv/xlsx/parquet/json file in and one click profiles it
  - Any plot the agent saves via plt.savefig(...) during a turn is shown inline in the chat
  - RAG sources panel lists everything scraped/crawled into the local doc store, with a
    clear-all button and per-source delete — the store itself always stays on this machine
    (a local Chroma DB on disk, see rag.py); this panel just lets you see/manage it.
"""

import asyncio
from pathlib import Path

import streamlit as st

import rag
from config import TIERS
from core import run_turn
from tools.files import WORKSPACE_DIR

st.set_page_config(page_title="Multi-Model Agent", page_icon="🤖", layout="wide")

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg"}
DATASET_SUFFIXES = {".csv", ".tsv", ".parquet", ".pq", ".xlsx", ".xls", ".json"}

TIER_BADGE = {"fast": "🟢", "balanced": "🟡", "deep": "🟣"}

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; max-width: 1100px; }
    [data-testid="stChatMessage"] { padding: 0.4rem 0; }
    .turn-meta {
        font-size: 0.78rem;
        color: var(--text-color, #888);
        opacity: 0.7;
        margin-top: -0.3rem;
    }
    .rag-source {
        font-size: 0.82rem;
        padding: 0.15rem 0;
        border-bottom: 1px solid rgba(128,128,128,0.15);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- session state -------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role", "content", "meta", "tool_calls", "images"}
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0.0
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None


def snapshot_images() -> dict[str, float]:
    if not WORKSPACE_DIR.exists():
        return {}
    return {
        str(p.relative_to(WORKSPACE_DIR)): p.stat().st_mtime
        for p in WORKSPACE_DIR.rglob("*")
        if p.suffix.lower() in IMAGE_SUFFIXES
    }


# --- sidebar ---------------------------------------------------------------

with st.sidebar:
    st.title("🤖 Multi-Model Agent")
    st.caption("Data-science assistant — EDA, feature engineering, and web-scraped RAG docs.")

    tier_choice = st.radio(
        "Model tier",
        options=["auto"] + list(TIERS.keys()),
        format_func=lambda t: "Auto (router picks)" if t == "auto" else f"{TIER_BADGE.get(t, '')} {t} — {TIERS[t].model}",
    )
    force_tier = None if tier_choice == "auto" else tier_choice

    st.metric("Total cost this session", f"${st.session_state.total_cost:.4f}")

    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = None
        st.session_state.total_cost = 0.0
        st.rerun()

    st.divider()
    st.subheader("📁 Dataset upload")
    uploaded = st.file_uploader(
        "Drop a csv/tsv/xlsx/parquet/json file",
        type=[s.lstrip(".") for s in DATASET_SUFFIXES],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        dest = WORKSPACE_DIR / uploaded.name
        dest.write_bytes(uploaded.getvalue())
        st.success(f"Saved to workspace/{uploaded.name}")
        if st.button(f"🔎 Profile {uploaded.name}", use_container_width=True):
            st.session_state.pending_prompt = (
                f"Load {uploaded.name} and give me a full EDA summary, including data quality "
                "issues and 2-3 suggested engineered features."
            )
            st.rerun()

    st.divider()
    st.subheader("📚 RAG doc store")
    st.caption("Stored locally on this machine — see ./rag_store")
    sources = rag.list_sources()
    if not sources:
        st.caption("Empty. Ask the agent to scrape_page or crawl_site a URL.")
    else:
        total_chunks = sum(s["chunks"] for s in sources)
        st.caption(f"{len(sources)} source(s), {total_chunks} chunk(s)")
        for s in sources:
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(
                    f"<div class='rag-source'><b>{s['title'] or s['source']}</b><br>"
                    f"<span style='opacity:0.6'>{s['source']} · {s['chunks']} chunks</span></div>",
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("✕", key=f"del-{s['source']}", help="Remove this source"):
                    rag.remove_source(s["source"])
                    st.rerun()

        if st.button("🗑️ Clear all RAG docs", use_container_width=True):
            rag.clear_store()
            st.rerun()

# --- main chat area ----------------------------------------------------

st.title("Chat")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("meta"):
            st.markdown(f"<div class='turn-meta'>{msg['meta']}</div>", unsafe_allow_html=True)
        for img_path in msg.get("images", []):
            full_path = WORKSPACE_DIR / img_path
            if full_path.exists():
                st.image(str(full_path), caption=img_path)
        for tool_name, tool_input in msg.get("tool_calls", []):
            with st.expander(f"🔧 {tool_name.split('__')[-1]}"):
                st.json(tool_input)

prompt = st.session_state.pending_prompt or st.chat_input("Ask me anything...")
st.session_state.pending_prompt = None

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    images_before = snapshot_images()

    with st.chat_message("assistant"):
        placeholder = st.empty()
        buffer = {"text": ""}
        tool_calls_seen = []

        def on_delta(chunk: str) -> None:
            buffer["text"] += chunk
            placeholder.markdown(buffer["text"] + "▌")

        def on_tool(name: str, tool_input: dict) -> None:
            tool_calls_seen.append((name, tool_input))
            short_name = name.split("__")[-1]
            placeholder.markdown(buffer["text"] + f"\n\n*↳ using `{short_name}`...*")

        result = asyncio.run(
            run_turn(
                prompt,
                session_id=st.session_state.session_id,
                force_tier=force_tier,
                on_text_delta=on_delta,
                on_tool_call=on_tool,
            )
        )

        if result.error:
            placeholder.error(result.error)
            final_text = f"⚠️ {result.error}"
            meta = None
        else:
            final_text = result.text or buffer["text"]
            placeholder.markdown(final_text)
            cost_str = f"${result.cost_usd:.4f}" if result.cost_usd is not None else "n/a"
            meta = f"{TIER_BADGE.get(result.tier, '')} {result.tier} · {result.model} · {cost_str}"
            st.markdown(f"<div class='turn-meta'>{meta}</div>", unsafe_allow_html=True)
            st.session_state.session_id = result.session_id
            st.session_state.total_cost += result.cost_usd or 0.0

        images_after = snapshot_images()
        new_images = sorted(
            [p for p, mtime in images_after.items() if images_before.get(p) != mtime]
        )
        for img_path in new_images:
            st.image(str(WORKSPACE_DIR / img_path), caption=img_path)

        for tool_name, tool_input in tool_calls_seen:
            with st.expander(f"🔧 {tool_name.split('__')[-1]}"):
                st.json(tool_input)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": final_text,
            "meta": meta,
            "tool_calls": tool_calls_seen,
            "images": new_images,
        }
    )
