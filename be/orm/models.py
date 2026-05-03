from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone

from orm.session import Base


class User(Base):
    """Stores Google OAuth users. google_id is the stable unique identifier."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
