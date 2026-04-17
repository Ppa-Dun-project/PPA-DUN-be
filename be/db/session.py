from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from core.config import settings

# Create SQLAlchemy engine using the DATABASE_URL from .env
engine = create_engine(settings.DATABASE_URL, echo=False)

# SessionLocal produces a new DB session per request
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Base class for all ORM models
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
