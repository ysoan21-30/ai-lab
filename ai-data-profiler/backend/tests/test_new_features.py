"""Tests for all new features: teams, connectors, rules, schedules, webhooks, audit, shared reports, Google OAuth."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.models import PlanTier, User

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine)


def override_get_db():
    db = TestSession()
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


def _create_user(plan: PlanTier = PlanTier.TEAM) -> tuple[str, dict]:
    """Create a user and return (token, headers)."""
    db = TestSession()
    user = User(
        email=f"test-{plan.value}@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Test User",
        plan=plan,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    db.close()
    return token, {"Authorization": f"Bearer {token}"}


client = TestClient(app)


# ====== Teams ======

class TestTeams:
    def test_create_team(self):
        _, headers = _create_user(PlanTier.TEAM)
        resp = client.post("/api/teams", json={"name": "My Team"}, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["name"] == "My Team"
        assert resp.json()["slug"] == "my-team"

    def test_list_teams(self):
        _, headers = _create_user(PlanTier.TEAM)
        client.post("/api/teams", json={"name": "Team A"}, headers=headers)
        resp = client.get("/api/teams", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_free_user_blocked(self):
        _, headers = _create_user(PlanTier.FREE)
        resp = client.post("/api/teams", json={"name": "Nope"}, headers=headers)
        assert resp.status_code == 403

    def test_invite_member(self):
        _, owner_headers = _create_user(PlanTier.TEAM)
        # Create team
        team = client.post("/api/teams", json={"name": "Invite Test"}, headers=owner_headers).json()
        # Create another user to invite
        db = TestSession()
        invitee = User(email="invitee@example.com", hashed_password=hash_password("pass12345"), plan=PlanTier.TEAM)
        db.add(invitee)
        db.commit()
        db.close()
        resp = client.post(f"/api/teams/{team['id']}/invite",
                           json={"email": "invitee@example.com", "role": "member"},
                           headers=owner_headers)
        assert resp.status_code == 201

    def test_list_members(self):
        _, headers = _create_user(PlanTier.TEAM)
        team = client.post("/api/teams", json={"name": "Members Test"}, headers=headers).json()
        resp = client.get(f"/api/teams/{team['id']}/members", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1  # owner


# ====== Custom Rules ======

class TestRules:
    def test_create_rule(self):
        _, headers = _create_user(PlanTier.PRO)
        resp = client.post("/api/rules", json={
            "name": "No nulls in email",
            "column_name": "email",
            "operator": "not_null",
            "severity": "critical",
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["operator"] == "not_null"

    def test_list_rules(self):
        _, headers = _create_user(PlanTier.PRO)
        client.post("/api/rules", json={"name": "R1", "operator": "not_null"}, headers=headers)
        resp = client.get("/api/rules", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_toggle_rule(self):
        _, headers = _create_user(PlanTier.PRO)
        rule = client.post("/api/rules", json={"name": "Toggle me", "operator": "unique", "column_name": "id"}, headers=headers).json()
        resp = client.patch(f"/api/rules/{rule['id']}/toggle", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_delete_rule(self):
        _, headers = _create_user(PlanTier.PRO)
        rule = client.post("/api/rules", json={"name": "Delete me", "operator": "not_null"}, headers=headers).json()
        resp = client.delete(f"/api/rules/{rule['id']}", headers=headers)
        assert resp.status_code == 204

    def test_free_user_blocked(self):
        _, headers = _create_user(PlanTier.FREE)
        resp = client.post("/api/rules", json={"name": "Nope", "operator": "not_null"}, headers=headers)
        assert resp.status_code == 403


# ====== Rules Engine ======

class TestRulesEngine:
    def _make_rule(self, **kwargs):
        """Create a mock rule object for testing the engine without SQLAlchemy."""
        from types import SimpleNamespace
        defaults = {"id": "r0", "name": "test", "column_name": None,
                     "operator": None, "value": None, "is_active": True}
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_evaluate_not_null(self):
        import pandas as pd
        from app.models.models import RuleOperator
        from app.services.rules_engine import evaluate_rule

        rule = self._make_rule(id="r1", name="No nulls", column_name="age",
                               operator=RuleOperator.NOT_NULL)
        df = pd.DataFrame({"age": [25, None, 30, None]})
        result = evaluate_rule(rule, df)
        assert result["passed"] is False
        assert result["violation_count"] == 2

    def test_evaluate_between(self):
        import pandas as pd
        from app.models.models import RuleOperator
        from app.services.rules_engine import evaluate_rule

        rule = self._make_rule(id="r2", name="Age range", column_name="age",
                               operator=RuleOperator.BETWEEN, value={"min": 18, "max": 65})
        df = pd.DataFrame({"age": [10, 25, 70, 30]})
        result = evaluate_rule(rule, df)
        assert result["passed"] is False
        assert result["violation_count"] == 2

    def test_evaluate_regex(self):
        import pandas as pd
        from app.models.models import RuleOperator
        from app.services.rules_engine import evaluate_rule

        rule = self._make_rule(id="r3", name="Email format", column_name="email",
                               operator=RuleOperator.REGEX, value=r"^[^@]+@[^@]+\.[^@]+$")
        df = pd.DataFrame({"email": ["a@b.com", "invalid", "x@y.org"]})
        result = evaluate_rule(rule, df)
        assert result["passed"] is False
        assert result["violation_count"] == 1


# ====== Webhooks ======

class TestWebhooks:
    def test_create_webhook(self):
        _, headers = _create_user(PlanTier.PRO)
        resp = client.post("/api/webhooks", json={
            "name": "My Hook",
            "url": "https://example.com/hook",
            "events": ["analysis.completed"],
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["events"] == ["analysis.completed"]

    def test_list_webhooks(self):
        _, headers = _create_user(PlanTier.PRO)
        client.post("/api/webhooks", json={"name": "H1", "url": "https://h1.com", "events": ["analysis.completed"]}, headers=headers)
        resp = client.get("/api/webhooks", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_invalid_event_rejected(self):
        _, headers = _create_user(PlanTier.PRO)
        resp = client.post("/api/webhooks", json={
            "name": "Bad", "url": "https://x.com", "events": ["invalid.event"],
        }, headers=headers)
        assert resp.status_code == 400

    def test_toggle_webhook(self):
        _, headers = _create_user(PlanTier.PRO)
        wh = client.post("/api/webhooks", json={"name": "Toggle", "url": "https://t.com", "events": ["analysis.completed"]}, headers=headers).json()
        resp = client.patch(f"/api/webhooks/{wh['id']}/toggle", headers=headers)
        assert resp.json()["is_active"] is False

    def test_available_events(self):
        resp = client.get("/api/webhooks/events")
        assert resp.status_code == 200
        assert "analysis.completed" in resp.json()["events"]


# ====== Audit ======

class TestAudit:
    def test_audit_log_created_on_team_create(self):
        _, headers = _create_user(PlanTier.TEAM)
        client.post("/api/teams", json={"name": "Audited Team"}, headers=headers)
        resp = client.get("/api/audit", headers=headers)
        assert resp.status_code == 200
        actions = [l["action"] for l in resp.json()]
        assert "create" in actions

    def test_free_user_blocked(self):
        _, headers = _create_user(PlanTier.FREE)
        resp = client.get("/api/audit", headers=headers)
        assert resp.status_code == 403


# ====== Scheduled Analysis ======

class TestSchedules:
    def test_create_schedule(self):
        _, headers = _create_user(PlanTier.PRO)
        resp = client.post("/api/schedules", json={
            "name": "Daily Check",
            "frequency": "daily",
            "source_type": "database",
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["frequency"] == "daily"
        assert resp.json()["next_run_at"] is not None

    def test_list_schedules(self):
        _, headers = _create_user(PlanTier.PRO)
        client.post("/api/schedules", json={"name": "S1", "frequency": "weekly"}, headers=headers)
        resp = client.get("/api/schedules", headers=headers)
        assert len(resp.json()) >= 1

    def test_toggle_schedule(self):
        _, headers = _create_user(PlanTier.PRO)
        sched = client.post("/api/schedules", json={"name": "Toggle", "frequency": "daily"}, headers=headers).json()
        resp = client.patch(f"/api/schedules/{sched['id']}/toggle", headers=headers)
        assert resp.json()["is_active"] is False

    def test_free_user_blocked(self):
        _, headers = _create_user(PlanTier.FREE)
        resp = client.post("/api/schedules", json={"name": "Nope", "frequency": "daily"}, headers=headers)
        assert resp.status_code == 403


# ====== Database Connectors ======

class TestConnectors:
    def test_create_connector(self):
        _, headers = _create_user(PlanTier.PRO)
        resp = client.post("/api/connectors", json={
            "name": "Test DB",
            "connector_type": "sqlite",
            "database_name": ":memory:",
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["connector_type"] == "sqlite"

    def test_list_connectors(self):
        _, headers = _create_user(PlanTier.PRO)
        client.post("/api/connectors", json={"name": "C1", "connector_type": "sqlite", "database_name": ":memory:"}, headers=headers)
        resp = client.get("/api/connectors", headers=headers)
        assert len(resp.json()) >= 1

    def test_free_user_blocked(self):
        _, headers = _create_user(PlanTier.FREE)
        resp = client.post("/api/connectors", json={"name": "N", "connector_type": "sqlite", "database_name": ":memory:"}, headers=headers)
        assert resp.status_code == 403

    def test_delete_connector(self):
        _, headers = _create_user(PlanTier.PRO)
        conn = client.post("/api/connectors", json={"name": "Del", "connector_type": "sqlite", "database_name": ":memory:"}, headers=headers).json()
        resp = client.delete(f"/api/connectors/{conn['id']}", headers=headers)
        assert resp.status_code == 204


# ====== Shared Reports ======

class TestSharedReports:
    def test_share_report(self):
        _, headers = _create_user(PlanTier.PRO)
        # Create an analysis first
        db = TestSession()
        from app.models.models import Analysis, AnalysisStatus
        user = db.query(User).filter(User.plan == PlanTier.PRO).first()
        analysis = Analysis(
            user_id=user.id,
            dataset_name="test.csv",
            file_size_bytes=1000,
            status=AnalysisStatus.COMPLETED,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        analysis_id = analysis.id
        db.close()

        resp = client.post("/api/reports/share", json={
            "analysis_id": analysis_id,
            "title": "My Shared Report",
        }, headers=headers)
        assert resp.status_code == 201
        assert "share_token" in resp.json()
        assert resp.json()["share_url"] is not None

    def test_view_shared_report(self):
        _, headers = _create_user(PlanTier.PRO)
        db = TestSession()
        from app.models.models import Analysis, AnalysisStatus
        user = db.query(User).filter(User.plan == PlanTier.PRO).first()
        analysis = Analysis(
            user_id=user.id,
            dataset_name="public.csv",
            file_size_bytes=500,
            status=AnalysisStatus.COMPLETED,
            quality_score=0.85,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        analysis_id = analysis.id
        db.close()

        share = client.post("/api/reports/share", json={"analysis_id": analysis_id}, headers=headers).json()
        # View without auth
        resp = client.get(f"/api/reports/shared/{share['share_token']}")
        assert resp.status_code == 200
        assert resp.json()["dataset_name"] == "public.csv"

    def test_free_user_blocked(self):
        _, headers = _create_user(PlanTier.FREE)
        resp = client.post("/api/reports/share", json={"analysis_id": "fake"}, headers=headers)
        assert resp.status_code == 403


# ====== Google OAuth Config ======

class TestGoogleOAuth:
    def test_config_endpoint(self):
        resp = client.get("/api/auth/google/config")
        assert resp.status_code == 200
        # OAuth is not configured in tests, so should be disabled
        assert resp.json()["enabled"] is False

    def test_oauth_disabled_returns_400(self):
        resp = client.post("/api/auth/google", json={"credential": "fake-token"})
        assert resp.status_code == 400
        assert "not configured" in resp.json()["detail"]
