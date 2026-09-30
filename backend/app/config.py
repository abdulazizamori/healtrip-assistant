from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (.env in development).
    Secrets (API key, DB password) never live in code or reach the frontend."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    llm_timeout_seconds: float = 25.0
    llm_retries: int = 1

    # Database — the API connects with the READ-ONLY role
    database_url: str = "postgresql://healtrip_agent_ro:readonly_dev_password@localhost:5432/healtrip"

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
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
