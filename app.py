"""Streamlit UI entrypoint for the fraud analysis RAG chatbot."""

import tempfile
from pathlib import Path

import streamlit as st

from src.chat import claude_client
from src.config import settings
from src.ingestion import loader
from src.retrieval import vector_store

st.set_page_config(page_title="Fraud Analysis Chatbot", page_icon="🔎")
st.title("Fraud Analysis Chatbot")
st.caption("RAG-powered assistant over your fraud knowledge base")

# --- Required API keys ---------------------------------------------------
missing_keys = [
    name
    for name, value in (
        ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
        ("VOYAGE_API_KEY", settings.voyage_api_key),
    )
    if not value
]
if missing_keys:
    st.error(
        f"Missing required environment variable(s): {', '.join(missing_keys)}.\n\n"
        "Copy `.env.example` to `.env` and fill in the missing value(s), then restart the app."
    )
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []


def _render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander("Sources"):
        for source in sources:
            name = source.get("source", "unknown")
            chunk_index = source.get("chunk_index", "?")
            st.markdown(f"- **{name}** (chunk {chunk_index})")


# --- Sidebar: document ingestion -----------------------------------------
with st.sidebar:
    st.header("Knowledge base")
    uploaded_files = st.file_uploader(
        "Upload fraud case documents (PDF or TXT)",
        type=["pdf", "txt"],
        accept_multiple_files=True,
    )
    st.caption(
        "Embedding respects Voyage AI's free-tier rate limit (3 requests/minute), "
        "so ingesting more than a few chunks can take a minute or more."
    )
    if st.button("Ingest documents", disabled=not uploaded_files):
        progress_text = st.empty()
        progress_bar = st.progress(0.0)

        def _on_progress(done: int, total: int) -> None:
            progress_text.text(f"Embedding chunk {done}/{total}...")
            progress_bar.progress(done / total)

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                for uploaded_file in uploaded_files:
                    (tmp_path / uploaded_file.name).write_bytes(uploaded_file.getbuffer())
                chunks = loader.load_documents(str(tmp_path))
                if chunks:
                    progress_text.text(f"Embedding chunk 0/{len(chunks)}...")
                    vector_store.add_documents(chunks, progress_callback=_on_progress)
        except Exception as exc:
            progress_text.empty()
            progress_bar.empty()
            st.error(f"Ingestion failed: {exc}")
        else:
            progress_text.empty()
            progress_bar.empty()
            if chunks:
                st.success(f"Ingested {len(chunks)} chunk(s) from {len(uploaded_files)} file(s).")
            else:
                st.warning("No text could be extracted from the uploaded file(s).")

# --- Main area: chat -------------------------------------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        _render_sources(message.get("sources", []))

question = st.chat_input("Ask about a case, pattern, or policy...")
if question:
    st.session_state.messages.append({"role": "user", "content": question, "sources": []})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = claude_client.answer_question(question)
            except Exception as exc:
                answer = f"Something went wrong while generating an answer: {exc}"
                sources = []
                st.error(answer)
            else:
                answer = result["answer"]
                sources = result["sources"]
                st.markdown(answer)
                _render_sources(sources)

    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
