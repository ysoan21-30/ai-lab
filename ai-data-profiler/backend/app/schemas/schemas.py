"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleOAuthRequest(BaseModel):
    credential: str  # Google ID token from frontend


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    auth_provider: str = "local"
    plan: str
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Analyses ---
class AnalysisSummary(BaseModel):
    id: str
    dataset_name: str
    status: str
    row_count: Optional[int]
    column_count: Optional[int]
    file_size_bytes: int
    quality_score: Optional[float]
    ml_readiness_score: Optional[float]
    issue_count: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class AnalysisDetail(AnalysisSummary):
    profile_result: Optional[Any] = None
    quality_result: Optional[Any] = None
    correlation_result: Optional[Any] = None
    target_result: Optional[Any] = None
    ml_readiness_result: Optional[Any] = None
    ai_insights: Optional[Any] = None
    charts: Optional[Any] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class SetTargetRequest(BaseModel):
    column: str


class UsageOut(BaseModel):
    plan: str
    analyses_used_this_month: int
    analyses_limit: int
    max_upload_mb: int


# --- Teams ---
class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class TeamOut(BaseModel):
    id: str
    name: str
    slug: str
    owner_id: str
    plan: str
    created_at: datetime
    member_count: Optional[int] = None

    class Config:
        from_attributes = True


class TeamMemberOut(BaseModel):
    id: str
    user_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True


class TeamInvite(BaseModel):
    email: EmailStr
    role: str = "member"  # member | viewer | admin


# --- Database Connectors ---
class DatabaseConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    connector_type: str  # postgresql | mysql | sqlite
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: str
    username: Optional[str] = None
    password: Optional[str] = None
    extra_params: Optional[dict] = None


class DatabaseConnectionOut(BaseModel):
    id: str
    name: str
    connector_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: str
    username: Optional[str] = None
    is_active: bool
    last_tested_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DatabaseQueryRequest(BaseModel):
    connection_id: str
    query: str = Field(max_length=10000)
    dataset_name: Optional[str] = "db_query_result"


# --- Scheduled Analysis ---
class ScheduledAnalysisCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: str = "database"  # upload | database
    connection_id: Optional[str] = None
    query: Optional[str] = None
    frequency: str  # hourly | daily | weekly | monthly
    cron_expression: Optional[str] = None
    alert_on_quality_drop: Optional[float] = None
    alert_on_row_count_change: Optional[float] = None
    alert_severity: str = "warning"
    alert_channels: Optional[List[str]] = None


class ScheduledAnalysisOut(BaseModel):
    id: str
    name: str
    source_type: str
    connection_id: Optional[str] = None
    frequency: str
    is_active: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    alert_on_quality_drop: Optional[float] = None
    alert_on_row_count_change: Optional[float] = None
    alert_severity: str
    alert_channels: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduleRunOut(BaseModel):
    id: str
    schedule_id: str
    analysis_id: Optional[str] = None
    status: str
    alerts_triggered: Optional[Any] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Custom Quality Rules ---
class CustomRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    column_name: Optional[str] = None
    operator: str  # not_null | unique | min | max | between | regex | in_list | custom_sql
    value: Optional[Any] = None
    severity: str = "warning"


class CustomRuleOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    column_name: Optional[str] = None
    operator: str
    value: Optional[Any] = None
    severity: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RuleEvaluationResult(BaseModel):
    rule_id: str
    rule_name: str
    passed: bool
    violation_count: int = 0
    violation_sample: Optional[List[Any]] = None
    message: str = ""


# --- Shareable Reports ---
class ShareReportCreate(BaseModel):
    analysis_id: str
    title: Optional[str] = None
    is_public: bool = True
    password: Optional[str] = None
    expires_in_days: Optional[int] = None


class ShareableReportOut(BaseModel):
    id: str
    analysis_id: str
    share_token: str
    title: Optional[str] = None
    is_public: bool
    has_password: bool = False
    expires_at: Optional[datetime] = None
    view_count: int
    created_at: datetime
    share_url: Optional[str] = None

    class Config:
        from_attributes = True


# --- Audit Log ---
class AuditLogOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Webhooks ---
class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(max_length=1000)
    secret: Optional[str] = None
    events: List[str]  # analysis.completed, alert.triggered, etc.


class WebhookOut(BaseModel):
    id: str
    name: str
    url: str
    events: List[str]
    is_active: bool
    last_triggered_at: Optional[datetime] = None
    failure_count: int
    created_at: datetime

    class Config:
        from_attributes = True
