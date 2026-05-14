from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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


class DraftPlayerNote(Base):
    """Per-session free-text memo a user can attach to a player.
    UNIQUE(session_id, player_id) — one note per player per session, upserted.
    FK on draft_sessions.id with CASCADE so notes auto-delete with the session.
    """
    __tablename__ = "draft_player_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("draft_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(100), nullable=False, index=True)
    player_id = Column(String(20), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("session_id", "player_id", name="uq_session_player_note"),
    )
