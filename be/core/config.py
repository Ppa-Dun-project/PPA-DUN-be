from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
_ENV_FILE = _BASE_DIR / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "My FastAPI"
    ENV: str = "dev"
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
