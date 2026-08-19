"""API integration tests using an in-memory SQLite DB (dependency-overridden)."""
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models import models  # noqa: F401

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def _register(email="user@example.com", password="StrongPass123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def test_register_creates_user_and_returns_token():
    resp = _register()
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["plan"] == "free"


def test_register_duplicate_email_rejected():
    _register()
    resp = _register()
    assert resp.status_code == 409


def test_login_success_and_failure():
    _register()
    ok = client.post("/api/auth/login", json={"email": "user@example.com", "password": "StrongPass123"})
    assert ok.status_code == 200

    bad = client.post("/api/auth/login", json={"email": "user@example.com", "password": "wrong"})
    assert bad.status_code == 401


def test_me_requires_authentication():
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user():
    token = _register()['json'] if False else _register().json()["access_token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


def _auth_headers(email="analyst@example.com"):
    token = _register(email=email).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _sample_csv_bytes() -> bytes:
    import numpy as np
    import pandas as pd
    np.random.seed(0)
    df = pd.DataFrame({
        "id": range(100),
        "age": np.random.randint(18, 60, 100),
        "category": np.random.choice(["a", "b", "c"], 100),
    })
    return df.to_csv(index=False).encode()


def test_upload_and_analyze_csv():
    headers = _auth_headers()
    files = {"file": ("test.csv", io.BytesIO(_sample_csv_bytes()), "text/csv")}
    resp = client.post("/api/analyses", headers=headers, files=files)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "completed"
    assert body["row_count"] == 100
    assert body["ml_readiness_score"] is not None


def test_reject_unsupported_file_extension():
    headers = _auth_headers()
    files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
    resp = client.post("/api/analyses", headers=headers, files=files)
    assert resp.status_code == 400


def test_reject_empty_file():
    headers = _auth_headers()
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    resp = client.post("/api/analyses", headers=headers, files=files)
    assert resp.status_code == 422


def test_list_analyses_returns_only_owner_data():
    headers_a = _auth_headers("a@example.com")
    headers_b = _auth_headers("b@example.com")
    files = {"file": ("test.csv", io.BytesIO(_sample_csv_bytes()), "text/csv")}
    client.post("/api/analyses", headers=headers_a, files=files)

    resp_a = client.get("/api/analyses", headers=headers_a)
    resp_b = client.get("/api/analyses", headers=headers_b)
    assert len(resp_a.json()) == 1
    assert len(resp_b.json()) == 0


def test_usage_limit_enforced_for_free_plan(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "free_analyses_per_month", 1)
    # plans module reads settings at import time via PLAN_DEFAULTS, so patch directly
    from app.billing import plans
    monkeypatch.setitem(plans.PLAN_DEFAULTS[plans.PlanTier.FREE], "analyses_per_month", 1)

    headers = _auth_headers("limited@example.com")
    files = {"file": ("test.csv", io.BytesIO(_sample_csv_bytes()), "text/csv")}
    first = client.post("/api/analyses", headers=headers, files=files)
    assert first.status_code == 201

    files2 = {"file": ("test2.csv", io.BytesIO(_sample_csv_bytes()), "text/csv")}
    second = client.post("/api/analyses", headers=headers, files=files2)
    assert second.status_code == 402


def test_export_csv_requires_ownership():
    headers_a = _auth_headers("owner@example.com")
    headers_b = _auth_headers("intruder@example.com")
    files = {"file": ("test.csv", io.BytesIO(_sample_csv_bytes()), "text/csv")}
    analysis_id = client.post("/api/analyses", headers=headers_a, files=files).json()["id"]

    resp = client.get(f"/api/analyses/{analysis_id}/export/csv", headers=headers_b)
    assert resp.status_code == 404


def test_health_check():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_manual_target_override_persists_across_requests():
    """Regression test: the target-result JSON column was previously mutated
    in place, which SQLAlchemy's change tracking doesn't detect for plain
    JSON columns -- db.commit() silently no-opped and the override appeared
    to work in the same request/response but reverted on the next read.
    """
    headers = _auth_headers("target-override@example.com")
    files = {"file": ("test.csv", io.BytesIO(_sample_csv_bytes()), "text/csv")}
    analysis_id = client.post("/api/analyses", headers=headers, files=files).json()["id"]

    set_resp = client.post(f"/api/analyses/{analysis_id}/target", headers=headers, json={"column": "category"})
    assert set_resp.status_code == 200
    assert set_resp.json()["target_result"]["most_likely_target"] == "category"
    assert set_resp.json()["target_result"]["confidence"] == 1.0

    # Re-fetch on a fresh request (new DB session) to confirm the override
    # actually persisted, not just reflected the in-memory object.
    refetched = client.get(f"/api/analyses/{analysis_id}", headers=headers)
    assert refetched.json()["target_result"]["most_likely_target"] == "category"
    assert refetched.json()["target_result"]["confidence"] == 1.0


def test_manual_target_override_rejects_unknown_column():
    headers = _auth_headers("target-invalid@example.com")
    files = {"file": ("test.csv", io.BytesIO(_sample_csv_bytes()), "text/csv")}
    analysis_id = client.post("/api/analyses", headers=headers, files=files).json()["id"]

    resp = client.post(f"/api/analyses/{analysis_id}/target", headers=headers, json={"column": "does_not_exist"})
    assert resp.status_code == 400
