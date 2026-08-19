"""Central config loaded from environment variables (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    voyage_api_key: str = os.getenv("VOYAGE_API_KEY", "")
    voyage_embedding_model: str = os.getenv("VOYAGE_EMBEDDING_MODEL", "voyage-3")

    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
    chroma_collection_name: str = os.getenv("CHROMA_COLLECTION_NAME", "fraud_knowledge_base")

    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
