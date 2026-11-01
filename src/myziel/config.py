"""Settings loaded from environment variables (pydantic-settings).

Secrets never live in the repo."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/myziel.db"
    secret_key: str = "change-me"
    # Set to true when served over HTTPS (production) so the session cookie is Secure.
    session_https_only: bool = False

    # smtp://user:pass@host:587 (STARTTLS) or smtps://user:pass@host:465. Empty = log only.
    smtp_url: str = ""
    mail_from: str = "myziel@localhost"
    base_url: str = "http://localhost:8000"

    scheduler_enabled: bool = True
    reminder_check_minutes: int = 15

    # Phase 2 (LLM extraction, web push). Unused in the MVP.
    llm_api_key: str = ""
    llm_monthly_budget_usd: float = 5
    vapid_private_key: str = ""

    log_level: str = "INFO"
    log_json: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
