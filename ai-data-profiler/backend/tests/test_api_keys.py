"""Tests for API key generation, validation, and management."""
import io

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.api_keys import create_api_key, hash_api_key, validate_api_key
from app.db.session import Base, get_db
from app.main import app
from app.models import models  # noqa: F401
from app.models.models import PlanTier, User

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def _register(email="team@example.com", password="StrongPass123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _auth_headers(email="team@example.com"):
    token = _register(email=email).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _promote_to_team(email: str):
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == email).first()
    user.plan = PlanTier.TEAM
    db.commit()
    db.close()


def test_create_api_key_requires_team_plan():
    headers = _auth_headers("free@example.com")
    resp = client.post("/api/keys", headers=headers, json={"label": "test"})
    assert resp.status_code == 403


def test_create_and_list_api_key():
    email = "teamuser@example.com"
    headers = _auth_headers(email)
    _promote_to_team(email)

    create_resp = client.post("/api/keys", headers=headers, json={"label": "CI key"})
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["raw_key"].startswith("adp_")
    assert body["label"] == "CI key"

    list_resp = client.get("/api/keys", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


def test_api_key_auth_works_for_uploads():
    email = "apiuser@example.com"
    headers = _auth_headers(email)
    _promote_to_team(email)

    create_resp = client.post("/api/keys", headers=headers, json={"label": "upload key"})
    raw_key = create_resp.json()["raw_key"]

    # Use API key (no Bearer token) to upload a dataset
    np.random.seed(0)
    df = pd.DataFrame({"a": range(50), "b": np.random.normal(0, 1, 50)})
    csv_bytes = df.to_csv(index=False).encode()
    files = {"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")}
    resp = client.post("/api/analyses", files=files, headers={"X-API-Key": raw_key})
    assert resp.status_code == 201
    assert resp.json()["status"] == "completed"


def test_revoke_api_key():
    email = "revoke@example.com"
    headers = _auth_headers(email)
    _promote_to_team(email)

    create_resp = client.post("/api/keys", headers=headers, json={"label": "temp"})
    key_id = create_resp.json()["id"]
    raw_key = create_resp.json()["raw_key"]

    # Revoke
    del_resp = client.delete(f"/api/keys/{key_id}", headers=headers)
    assert del_resp.status_code == 204

    # Revoked key should not authenticate
    files = {"file": ("test.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")}
    resp = client.post("/api/analyses", files=files, headers={"X-API-Key": raw_key})
    assert resp.status_code == 401


def test_invalid_api_key_rejected():
    files = {"file": ("test.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")}
    resp = client.post("/api/analyses", files=files, headers={"X-API-Key": "adp_fake123"})
    assert resp.status_code == 401
