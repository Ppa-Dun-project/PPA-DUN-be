# Public notification endpoint used by the Draft Kit frontend.
# FE polls GET /api/notifications/recent?since=<id> every 15 seconds and
# fires a toast for each new event.
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from database.notification_store import list_since
from orm.session import engine
from security import get_user_id

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationItem(BaseModel):
    id: int
    event_type: str
    player_id: str
    player_name: Optional[str] = None
    message: str
    # ISO 8601 string so the FE can hand it straight to new Date(...).
    created_at: str


class NotificationList(BaseModel):
    items: List[NotificationItem]
    # Highest notification id currently in the table. FE uses this on the very
    # first poll of a session to skip all historic events (so a new user
    # doesn't get a flood of stale notifications).
    latest_id: int


@router.get("/recent", response_model=NotificationList)
def list_recent_notifications(
    since: int = Query(0, ge=0, description="Last id the client has seen"),
    limit: int = Query(50, ge=1, le=200),
    current_user_id: int = Depends(get_user_id),  # 인증만 필요 — user_id 자체는 안 씀
):
    """Return notifications with id > since (oldest first), plus the current
    table-wide latest_id so the FE can anchor at 'now' on first load."""
    rows = list_since(last_id=since, limit=limit)
    items = [
        NotificationItem(
            id=r["id"],
            event_type=r["event_type"],
            player_id=str(r["player_id"]),
            player_name=r["player_name"],
            message=r["message"],
            created_at=r["created_at"].isoformat() if r["created_at"] else "",
        )
        for r in rows
    ]

    with engine.connect() as conn:
        max_id = conn.execute(
            text("SELECT COALESCE(MAX(id), 0) FROM notifications")
        ).scalar()

    return NotificationList(items=items, latest_id=int(max_id or 0))
