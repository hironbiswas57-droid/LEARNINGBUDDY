"""Environment-driven application configuration."""

from dataclasses import dataclass
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_local_env() -> None:
    """Load a simple project .env file without overriding real environment values."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


_load_local_env()


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("LEARNMATE_ENV", "development")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    database_path: str = os.getenv("DATABASE_PATH", str(ROOT / "data" / "learnmate.db"))
    jwt_secret: str = os.getenv("JWT_SECRET", "local-development-only-change-me")
    access_token_minutes: int = int(os.getenv("JWT_ACCESS_EXPIRY_MINUTES", "20"))
    refresh_token_days: int = int(os.getenv("JWT_REFRESH_EXPIRY_DAYS", "14"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    reviewer_model: str = os.getenv("REVIEWER_MODEL", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    request_rate_per_minute: int = int(os.getenv("REQUEST_RATE_PER_MINUTE", "120"))


settings = Settings()
