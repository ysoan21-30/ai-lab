"""Database connector CRUD + query execution routes (PRO + TEAM)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import ConnectorType, DatabaseConnection, PlanTier, User
from app.schemas.schemas import (
    DatabaseConnectionCreate, DatabaseConnectionOut, DatabaseQueryRequest,
)
from app.services.db_connector import list_tables, run_query, test_connection

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


def _require_pro_or_team(user: User):
    if user.plan == PlanTier.FREE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Database connectors require Pro or Team plan.")


@router.post("", response_model=DatabaseConnectionOut, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: DatabaseConnectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_pro_or_team(user)
    try:
        ct = ConnectorType(payload.connector_type)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported type: {payload.connector_type}")

    conn = DatabaseConnection(
        user_id=user.id,
        name=payload.name,
        connector_type=ct,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        encrypted_password=payload.password,  # TODO: encrypt at rest
        extra_params=payload.extra_params,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.get("", response_model=list[DatabaseConnectionOut])
def list_connections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_pro_or_team(user)
    return db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == user.id,
        DatabaseConnection.is_active == True,
    ).order_by(DatabaseConnection.created_at.desc()).all()


@router.post("/{conn_id}/test")
def test_conn(
    conn_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == conn_id,
        DatabaseConnection.user_id == user.id,
    ).first()
    if not conn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found.")
    result = test_connection(conn)
    conn.last_tested_at = datetime.utcnow()
    db.commit()
    return result


@router.get("/{conn_id}/tables")
def get_tables(
    conn_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_pro_or_team(user)
    conn = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == conn_id,
        DatabaseConnection.user_id == user.id,
    ).first()
    if not conn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found.")
    try:
        tables = list_tables(conn)
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/query")
def execute_query(
    payload: DatabaseQueryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run a SELECT query against a connector and return a preview + analysis-ready summary."""
    _require_pro_or_team(user)
    conn = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == payload.connection_id,
        DatabaseConnection.user_id == user.id,
    ).first()
    if not conn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found.")
    try:
        df = run_query(conn, payload.query)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Query failed: {e}")

    # Return preview
    preview_rows = df.head(50).to_dict(orient="records")
    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(df[col].dtype) for col in df.columns},
        "preview": preview_rows,
        "dataset_name": payload.dataset_name,
    }


@router.delete("/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    conn_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == conn_id,
        DatabaseConnection.user_id == user.id,
    ).first()
    if not conn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found.")
    conn.is_active = False
    db.commit()
