"""Streamlit UI entrypoint for the fraud analysis RAG chatbot.

TODO: wire up chat history, retrieval calls, and streamed Claude responses.
"""

import streamlit as st

st.set_page_config(page_title="Fraud Analysis Chatbot", page_icon="🔎")
st.title("Fraud Analysis Chatbot")
st.caption("RAG-powered assistant over your fraud knowledge base (scaffold — not yet wired up)")

st.chat_input("Ask about a case, pattern, or policy...")
