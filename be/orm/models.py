from sqlalchemy import (
    Column,
    DateTime,
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
    NOTE: session_id is logically a FK to draft_sessions.id, but draft_sessions is
    not an ORM-managed model. Declaring a SQLAlchemy ForeignKey here makes create_all
    fail at metadata sort time, so the constraint is omitted and session deletion
    must explicitly clean up notes (see database/draft_store.delete_session).
    """
    __tablename__ = "draft_player_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, nullable=False, index=True)
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


class Notification(Base):
    """Notification event displayed as a toast in the Draft Kit.
    Inserts come from two sources:
      1. delta detection during refresh_player_cache (real changes pulled from api)
      2. webhook from api's POST /admin/player-event (fake admin push for demos)
    Browser clients poll GET /api/notifications/recent?since=<id> every 15 seconds.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(32), nullable=False)
    player_id = Column(String(20), nullable=False, index=True)
    player_name = Column(String(255), nullable=True)
    message = Column(String(500), nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
