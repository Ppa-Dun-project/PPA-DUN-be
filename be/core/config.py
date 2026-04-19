# Application settings loaded from backend/.env via pydantic-settings.
# Includes CORS origins, external PPA API connection details, and timeout config.
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
_ENV_FILE = _BASE_DIR / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "My FastAPI"
    ENV: str = "dev"
    CORS_ORIGINS: str = ""
    EXTERNAL_API_BASE_URL: str = ""
    EXTERNAL_API_KEY: str = ""
    EXTERNAL_API_TIMEOUT_SECONDS: float = 5.0

    GOOGLE_CLIENT_ID: str = ""
    DATABASE_URL: str = "mysql+pymysql://root:1234@localhost:3306/ppadun"

    GCP_PROJECT_ID: str = ""
    GCP_LOCATION: str = "us-east1"
    VERTEX_AI_MODEL: str = "gemini-2.0-flash-001"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
