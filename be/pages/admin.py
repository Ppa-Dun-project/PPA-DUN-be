# Admin / internal endpoints for the notification system.
#   POST /internal/notify       — webhook receiver from the Player API
#                                 (api's POST /admin/player-event forwards here)
#   POST /admin/notify          — direct fake push from be itself (demo shortcut)
#   POST /admin/refresh-cache   — force-trigger refresh_player_cache (live demo)
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database.notification_store import insert as insert_notification
from database.player_cache_store import refresh_player_cache

logger = logging.getLogger(__name__)


router = APIRouter(tags=["admin"])


class NotifyPayload(BaseModel):
    player_id: str
    message: str
    event_type: str = "INJURY"
    player_name: Optional[str] = None


def _check_admin_key(request: Request) -> None:
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret:
        raise HTTPException(status_code=503, detail="ADMIN_SECRET not configured")
    key = request.headers.get("X-Admin-Key")
    if not key or key != admin_secret:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Key")


def _check_internal_key(request: Request) -> None:
    internal_key = os.getenv("INTERNAL_WEBHOOK_KEY")
    if not internal_key:
        raise HTTPException(status_code=503, detail="INTERNAL_WEBHOOK_KEY not configured")
    key = request.headers.get("X-Internal-Key")
    if not key or key != internal_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Internal-Key")


@router.post("/internal/notify")
def receive_notify_webhook(payload: NotifyPayload, request: Request):
    """Webhook receiver called by the Player API's POST /admin/player-event.
    Inserts the event into the notifications table so FE polls pick it up."""
    _check_internal_key(request)
    inserted = insert_notification(
        event_type=payload.event_type,
        player_id=payload.player_id,
        message=payload.message,
        player_name=payload.player_name,
    )
    logger.info(f"[internal/notify] inserted notification id={inserted['id']}")
    return {"status": "ok", "id": inserted["id"]}


@router.post("/admin/notify")
def admin_fake_notify(payload: NotifyPayload, request: Request):
    """Direct fake-push entry on the be side — bypasses the Player API.
    Useful for demo when api cascade is not set up or for be-only testing."""
    _check_admin_key(request)
    inserted = insert_notification(
        event_type=payload.event_type,
        player_id=payload.player_id,
        message=payload.message,
        player_name=payload.player_name,
    )
    logger.info(f"[admin/notify] inserted notification id={inserted['id']}")
    return {"status": "ok", "id": inserted["id"]}


@router.post("/admin/refresh-cache")
async def admin_refresh_cache(request: Request):
    """Force-run refresh_player_cache immediately (skip the 15-min wait).
    Will detect deltas vs current cache and emit notifications inline."""
    _check_admin_key(request)
    try:
        await refresh_player_cache()
    except Exception as e:
        logger.error(f"[admin/refresh-cache] failed: {e}")
        raise HTTPException(status_code=500, detail=f"refresh failed: {e}")
    return {"status": "refreshed"}
