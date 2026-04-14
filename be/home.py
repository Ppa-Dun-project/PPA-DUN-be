# Home page API router.
# Will handle Google login and other home page features.
import os

from dotenv import load_dotenv
from fastapi import APIRouter
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
_engine = create_engine(DATABASE_URL)

router = APIRouter(prefix="/api", tags=["home"])
