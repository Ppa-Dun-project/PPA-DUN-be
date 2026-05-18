# CRUD for the notifications table.
# Insert is called from two places:
#   1. delta detection in refresh_player_cache (real injury/depth changes)
#   2. webhook receiver for fake admin pushes from the Player API
# list_since is what the FE polls every 15 seconds.
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import text

from orm.session import engine


def insert(
    event_type: str,
    player_id: str,
    message: str,
    player_name: Optional[str] = None,
) -> dict:
    """Insert a notification row. Returns the inserted row metadata so callers
    can publish in-process (e.g. to an SSE bus) if that's added later."""
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO notifications
                    (event_type, player_id, player_name, message, created_at)
                VALUES
                    (:event_type, :player_id, :player_name, :message, :now)
            """),
            {
                "event_type": event_type,
                "player_id": player_id,
                "player_name": player_name,
                "message": message,
                "now": now,
            },
        )
        return {
            "id": result.lastrowid,
            "event_type": event_type,
            "player_id": player_id,
            "player_name": player_name,
            "message": message,
            "created_at": now,
        }


def list_since(last_id: int = 0, limit: int = 50) -> List[dict]:
    """Return notifications newer than last_id, oldest first, capped at limit.
    FE polls this every 15 seconds with the highest id it has seen."""
    sql = text("""
        SELECT id, event_type, player_id, player_name, message, created_at
        FROM notifications
        WHERE id > :last_id
        ORDER BY id ASC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"last_id": last_id, "limit": limit}).fetchall()
    return [
        {
            "id": r._mapping["id"],
            "event_type": r._mapping["event_type"],
            "player_id": r._mapping["player_id"],
            "player_name": r._mapping["player_name"],
            "message": r._mapping["message"],
            "created_at": r._mapping["created_at"],
        }
        for r in rows
    ]
