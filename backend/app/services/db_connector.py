"""Database connector service — connects to external databases and runs queries."""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

from app.models.models import ConnectorType, DatabaseConnection

logger = logging.getLogger(__name__)

# Maximum rows returned from a query to prevent memory issues
MAX_QUERY_ROWS = 100_000


def _build_connection_url(conn: DatabaseConnection, password: Optional[str] = None) -> str:
    """Build a SQLAlchemy connection URL from a DatabaseConnection model."""
    ct = conn.connector_type
    pw = password or conn.encrypted_password or ""

    if ct == ConnectorType.SQLITE:
        return f"sqlite:///{conn.database_name}"

    user_part = conn.username or ""
    if pw:
        user_part = f"{user_part}:{pw}"

    host = conn.host or "localhost"
    port = conn.port

    if ct == ConnectorType.POSTGRESQL:
        port = port or 5432
        return f"postgresql://{user_part}@{host}:{port}/{conn.database_name}"
    elif ct == ConnectorType.MYSQL:
        port = port or 3306
        return f"mysql+pymysql://{user_part}@{host}:{port}/{conn.database_name}"

    raise ValueError(f"Unsupported connector type: {ct}")


def test_connection(conn: DatabaseConnection, password: Optional[str] = None) -> dict:
    """Test a database connection and return status."""
    try:
        url = _build_connection_url(conn, password)
        engine = create_engine(url, connect_args={"connect_timeout": 10} if conn.connector_type != ConnectorType.SQLITE else {})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        logger.warning("Connection test failed for %s: %s", conn.name, e)
        return {"success": False, "message": str(e)}


def run_query(conn: DatabaseConnection, query: str, password: Optional[str] = None) -> pd.DataFrame:
    """Execute a SELECT query and return results as a DataFrame.

    Only SELECT statements are allowed for safety.
    """
    stripped = query.strip().rstrip(";").strip()
    first_word = stripped.split()[0].upper() if stripped else ""
    if first_word not in ("SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"):
        raise ValueError("Only SELECT/WITH/SHOW/DESCRIBE queries are allowed for safety.")

    url = _build_connection_url(conn, password)
    engine = create_engine(url)
    try:
        df = pd.read_sql(text(query), engine)
        if len(df) > MAX_QUERY_ROWS:
            df = df.head(MAX_QUERY_ROWS)
            logger.info("Query result truncated to %d rows", MAX_QUERY_ROWS)
        return df
    finally:
        engine.dispose()


def list_tables(conn: DatabaseConnection, password: Optional[str] = None) -> list[str]:
    """List all tables in the connected database."""
    url = _build_connection_url(conn, password)
    engine = create_engine(url)
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        return inspector.get_table_names()
    finally:
        engine.dispose()
