"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql://profiler:profiler@localhost:5432/ai_data_profiler"

    # Auth
    secret_key: str = "insecure-dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    stripe_price_id_team: str = ""

    # Razorpay (future)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # App
    environment: str = "development"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # File handling
    upload_dir: str = "/tmp/ai-data-profiler-uploads"
    max_upload_mb_free: int = 10
    max_upload_mb_pro: int = 100
    max_upload_mb_team: int = 500
    file_retention_hours: int = 24

    # Plan limits
    free_analyses_per_month: int = 3
    pro_analyses_per_month: int = 50
    team_analyses_per_month: int = 500
    pro_price_inr: int = 499
    team_price_inr: int = 1999

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Background scheduler (polls ScheduledAnalysis rows in-process)
    enable_scheduler: bool = True
    scheduler_poll_seconds: int = 60

    # Notifications
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "alerts@aidataprofiler.com"
    slack_webhook_url: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_user)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
