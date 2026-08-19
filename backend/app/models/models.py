"""SQLAlchemy ORM models."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer,
    JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.types import GUID as UUID

# Re-export for convenience -- other modules can do:
#   from app.models.models import UUID, gen_uuid, MutableJSON

# In-place mutation of a plain JSON column's dict (e.g. `analysis.target_result["x"] = y`)
# is invisible to SQLAlchemy's change tracking -- db.commit() silently no-ops and a
# subsequent db.refresh() reverts to the stale stored value. Wrapping JSON columns that
# are ever mutated after initial write in MutableDict closes off that whole bug class;
# a plain reassignment (`analysis.target_result = {...}`) continues to work as before.
MutableJSON = MutableDict.as_mutable(JSON)


def gen_uuid():
    return str(uuid.uuid4())


class PlanTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TeamRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class RuleOperator(str, enum.Enum):
    NOT_NULL = "not_null"
    UNIQUE = "unique"
    MIN = "min"
    MAX = "max"
    BETWEEN = "between"
    REGEX = "regex"
    IN_LIST = "in_list"
    CUSTOM_SQL = "custom_sql"


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ScheduleFrequency(str, enum.Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    EXPORT = "export"
    SHARE = "share"
    INVITE = "invite"
    REVOKE = "revoke"


class ConnectorType(str, enum.Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # nullable for OAuth users
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    auth_provider = Column(String(50), default="local", nullable=False)  # local | google
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    plan = Column(Enum(PlanTier), default=PlanTier.FREE, nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    analyses = relationship("Analysis", back_populates="owner", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")
    team_memberships = relationship("TeamMember", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_name = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)

    # Results (JSON blobs keep the schema simple and extensible for an MVP)
    profile_result = Column(JSON, nullable=True)          # column-by-column profiling
    quality_result = Column(JSON, nullable=True)           # data quality issues
    correlation_result = Column(JSON, nullable=True)
    target_result = Column(MutableJSON, nullable=True)
    ml_readiness_result = Column(JSON, nullable=True)
    ai_insights = Column(JSON, nullable=True)
    charts = Column(JSON, nullable=True)

    quality_score = Column(Float, nullable=True)
    ml_readiness_score = Column(Float, nullable=True)
    issue_count = Column(Integer, nullable=True)

    processing_time_ms = Column(Integer, nullable=True)
    llm_tokens_used = Column(Integer, nullable=True)
    llm_cost_usd = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="analyses")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(UUID(), ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    file_size_bytes = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    column_count = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    llm_tokens_used = Column(Integer, nullable=True)
    plan = Column(Enum(PlanTier), nullable=False)

    user = relationship("User", back_populates="usage_records")


class Plan(Base):
    """Runtime-configurable pricing plans (avoids hardcoding pricing in app code)."""
    __tablename__ = "plans"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    tier = Column(Enum(PlanTier), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    price_inr = Column(Integer, nullable=False, default=0)
    analyses_per_month = Column(Integer, nullable=False)
    max_upload_mb = Column(Integer, nullable=False)
    features = Column(JSON, nullable=True)


class ApiKey(Base):
    """Optional API keys for TEAM plan API access."""
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("key_hash", name="uq_api_key_hash"),)

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String(255), nullable=False)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)


# ---------------------------------------------------------------------------
# Team workspaces
# ---------------------------------------------------------------------------

class Team(Base):
    __tablename__ = "teams"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    owner_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan = Column(Enum(PlanTier), default=PlanTier.TEAM, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    owner = relationship("User", foreign_keys=[owner_id])


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_user"),)

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    team_id = Column(UUID(), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum(TeamRole), default=TeamRole.MEMBER, nullable=False)
    invited_by = Column(UUID(), nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")


# ---------------------------------------------------------------------------
# Database connectors (PRO + TEAM)
# ---------------------------------------------------------------------------

class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(UUID(), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    connector_type = Column(Enum(ConnectorType), nullable=False)
    host = Column(String(500), nullable=True)
    port = Column(Integer, nullable=True)
    database_name = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True)
    encrypted_password = Column(Text, nullable=True)  # encrypted at rest
    extra_params = Column(JSON, nullable=True)  # SSL options, etc.
    is_active = Column(Boolean, default=True, nullable=False)
    last_tested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Scheduled analysis + alerts (PRO + TEAM)
# ---------------------------------------------------------------------------

class ScheduledAnalysis(Base):
    __tablename__ = "scheduled_analyses"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(UUID(), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    # Source: either a DB connection + query, or a re-upload trigger
    connection_id = Column(UUID(), ForeignKey("database_connections.id", ondelete="SET NULL"), nullable=True)
    query = Column(Text, nullable=True)  # SQL query for DB source
    source_type = Column(String(50), default="upload", nullable=False)  # upload | database
    frequency = Column(Enum(ScheduleFrequency), nullable=False)
    cron_expression = Column(String(100), nullable=True)  # custom cron override
    is_active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    # Alert thresholds
    alert_on_quality_drop = Column(Float, nullable=True)  # e.g. 0.1 = 10% quality score drop
    alert_on_row_count_change = Column(Float, nullable=True)  # e.g. 0.5 = 50% row count change
    alert_severity = Column(Enum(AlertSeverity), default=AlertSeverity.WARNING, nullable=False)
    alert_channels = Column(JSON, nullable=True)  # ["email", "slack", "webhook"]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    connection = relationship("DatabaseConnection", foreign_keys=[connection_id])


class ScheduleRun(Base):
    """Individual run record of a scheduled analysis."""
    __tablename__ = "schedule_runs"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    schedule_id = Column(UUID(), ForeignKey("scheduled_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(UUID(), ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False)
    alerts_triggered = Column(JSON, nullable=True)  # list of alert messages
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Custom quality rules (PRO + TEAM)
# ---------------------------------------------------------------------------

class CustomRule(Base):
    __tablename__ = "custom_rules"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(UUID(), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    column_name = Column(String(255), nullable=True)  # null = applies to whole dataset
    operator = Column(Enum(RuleOperator), nullable=False)
    value = Column(JSON, nullable=True)  # operator-specific: threshold, regex, list, etc.
    severity = Column(Enum(AlertSeverity), default=AlertSeverity.WARNING, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Shareable reports
# ---------------------------------------------------------------------------

class ShareableReport(Base):
    __tablename__ = "shareable_reports"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    analysis_id = Column(UUID(), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    share_token = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=True)
    is_public = Column(Boolean, default=True, nullable=False)
    password_hash = Column(String(255), nullable=True)  # optional password protection
    expires_at = Column(DateTime, nullable=True)
    view_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    analysis = relationship("Analysis", foreign_keys=[analysis_id])


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = Column(UUID(), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    action = Column(Enum(AuditAction), nullable=False)
    resource_type = Column(String(100), nullable=False)  # analysis, team, rule, connector, etc.
    resource_id = Column(String(255), nullable=True)
    details = Column(JSON, nullable=True)  # action-specific metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="audit_logs")


# ---------------------------------------------------------------------------
# Webhook + notification config
# ---------------------------------------------------------------------------

class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(UUID(), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(UUID(), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1000), nullable=False)
    secret = Column(String(255), nullable=True)  # HMAC signing secret
    events = Column(JSON, nullable=False)  # ["analysis.completed", "alert.triggered", ...]
    is_active = Column(Boolean, default=True, nullable=False)
    last_triggered_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
