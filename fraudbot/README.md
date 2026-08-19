# Fraud Analysis Chatbot (RAG)

A retrieval-augmented chatbot for fraud analysis, built on the Anthropic API,
ChromaDB for vector storage, and Streamlit for the UI.

> **Status:** ingestion (`src/ingestion/loader.py`), retrieval
> (`src/retrieval/vector_store.py`), and the RAG chat loop
> (`src/chat/claude_client.py`) are implemented. Only the Streamlit UI
> wiring (`app.py`) is left as a stub.

## Project structure

```
fraudbot/
├── app.py                  # Streamlit entrypoint
├── requirements.txt
├── .env.example            # copy to .env and fill in secrets
├── src/
│   ├── config.py           # env-based settings
│   ├── ingestion/          # document loading + chunking
│   │   └── loader.py
│   ├── retrieval/          # ChromaDB vector store
│   │   └── vector_store.py
│   ├── chat/                # Claude API client + RAG prompt logic
│   │   └── claude_client.py
│   └── utils/
├── data/
│   ├── raw/                # source documents (tracked)
│   ├── processed/          # chunked/cleaned text (gitignored)
│   └── chroma_db/          # persisted vector DB (gitignored)
├── tests/
└── .streamlit/
    └── config.toml
```

## Setup

```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # then fill in ANTHROPIC_API_KEY
```

`ANTHROPIC_MODEL` defaults to `claude-sonnet-5` — a good balance of quality,
speed, and cost for fraud-analysis Q&A. Switch to `claude-opus-5` in `.env`
if you need the most capable model for harder analytical tasks.

## Run

```bash
streamlit run app.py
```

## Testing

```bash
pytest                    # fast suite — no network calls, safe to run anytime
pytest -m integration     # also hits real Voyage AI + Anthropic APIs (needs VOYAGE_API_KEY, ANTHROPIC_API_KEY)
```

## Next steps

1. Wire `app.py` up to `src.chat.claude_client.answer_question` with streamed responses.
