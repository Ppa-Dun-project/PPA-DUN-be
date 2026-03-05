from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    APP_NAME: str = "PPA-Dun API"
    ENV: str = "dev"
    DATABASE_URL: str  # mysql+pymysql://user:pass@host:3306/dbname
    CORS_ORIGINS: str = "http://localhost:5173"

settings = Settings()