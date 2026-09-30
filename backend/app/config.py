from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (.env in development).
    Secrets (API key, DB password) never live in code or reach the frontend."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    # comma-separated; used only while the primary model is out of quota (429) or overloaded (503)
    gemini_fallback_models: str = "gemini-3.5-flash,gemini-3-flash-preview,gemini-3.5-flash-lite"
    # Claude: backup provider, used only while every Gemini model is unavailable (optional)
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "low"  # low keeps a chat turn fast; the server validates every answer regardless
    claude_timeout_seconds: float = 30.0
    llm_timeout_seconds: float = 25.0
    llm_retries: int = 1

    # Database — the API connects with the READ-ONLY role
    database_url: str = "postgresql://healtrip_agent_ro:readonly_dev_password@localhost:5432/healtrip"
    # Single-service hosting only (Render): the owner URL is used once at startup to create the schema and the
    # read-only role (app/bootstrap.py); the app itself then connects as the read-only role.
    admin_database_url: str = ""
    db_sql_dir: str = "/app/db"
    static_dir: str = "/app/static"  # exported frontend, served at / when present

    # HTTP
    allowed_origins: str = "http://localhost:3000"  # comma-separated
    rate_limit_per_minute: int = 20

    # Agent guardrails
    max_message_chars: int = 1000
    max_clarifying_questions: int = 4
    max_agent_steps_per_turn: int = 6
    max_invalid_outputs_per_turn: int = 2
    max_user_turns_per_session: int = 20
    session_ttl_minutes: int = 60

    @property
    def fallback_models(self) -> list[str]:
        return [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
