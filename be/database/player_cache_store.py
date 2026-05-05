# Batter and pitcher cache tables backed by the external PPA API.
# refresh_player_cache() pulls AL+NL batters and pitchers and upserts local cache.
import asyncio
import logging
from typing import Any

from sqlalchemy import text

from orm.session import engine
from ppa_api.ppa_client import build_ppa_api_client

logger = logging.getLogger(__name__)

BATTER_CACHE_TABLE = "batter_caching"
PITCHER_CACHE_TABLE = "pitcher_caching"

_BATTER_CACHE_COLUMNS = (
    "player_id", "name", "position", "team",
    "primary_number", "birth_date", "birth_city", "birth_country",
    "height", "weight", "current_age", "mlb_debut_date",
    "bat_side", "pitch_hand",
    "ab", "r", "h", "single", "double", "triple",
    "hr", "rbi", "bb", "k", "sb", "cs",
    "avg", "obp", "slg",
    "injury_status", "depth_order", "player_value",
)

_PITCHER_CACHE_COLUMNS = (
    "player_id", "name", "position", "team",
    "w", "sv", "so", "era", "whip", "ip",
    "injury_status", "depth_order", "player_value",
    "l", "g", "gs", "war", "fip", "h", "r", "er", "hr", "bb", "hbp", "bf",
    "era_plus", "h9", "hr9", "bb9", "so9", "so_bb",
    "primary_number", "birth_date", "birth_city", "birth_country",
    "height", "weight", "current_age", "mlb_debut_date", "pitch_hand",
)


def _extract_rows(response: dict[str, Any], preferred_key: str) -> list[dict[str, Any]]:
    rows = response.get(preferred_key)
    if rows is None:
        rows = response.get("players")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _upsert_cache_rows(table_name: str, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    quoted_cols = ", ".join(f"`{col}`" for col in columns)
    placeholders = ", ".join(f":{col}" for col in columns)
    update_clause = ", ".join(
        f"`{col}` = VALUES(`{col}`)" for col in columns if col != "player_id"
    )
    sql = text(f"""
        INSERT INTO {table_name} ({quoted_cols})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """)

    with engine.begin() as conn:
        conn.execute(sql, rows)


async def refresh_batter_cache() -> None:
    client = build_ppa_api_client()
    try:
        al_resp, nl_resp = await asyncio.gather(
            client.batters_by_league("AL", columns=_BATTER_CACHE_COLUMNS),
            client.batters_by_league("NL", columns=_BATTER_CACHE_COLUMNS),
        )
    except Exception as exc:
        logger.warning("batter cache refresh failed: %s", exc)
        return

    batters = _extract_rows(al_resp, "batters") + _extract_rows(nl_resp, "batters")
    rows = [
        {col: batter.get(col) for col in _BATTER_CACHE_COLUMNS}
        for batter in batters
        if batter.get("player_id") is not None
    ]

    if not rows:
        logger.warning("batter cache refresh: no batters returned from API")
        return

    _upsert_cache_rows(BATTER_CACHE_TABLE, _BATTER_CACHE_COLUMNS, rows)
    logger.info("batter cache refresh: %d batters upserted", len(rows))


async def refresh_pitcher_cache() -> None:
    client = build_ppa_api_client()
    try:
        al_resp, nl_resp = await asyncio.gather(
            client.pitchers_by_league("AL", columns=_PITCHER_CACHE_COLUMNS),
            client.pitchers_by_league("NL", columns=_PITCHER_CACHE_COLUMNS),
        )
    except Exception as exc:
        logger.warning("pitcher cache refresh failed: %s", exc)
        return

    pitchers = _extract_rows(al_resp, "pitchers") + _extract_rows(nl_resp, "pitchers")
    rows = [
        {col: pitcher.get(col) for col in _PITCHER_CACHE_COLUMNS}
        for pitcher in pitchers
        if pitcher.get("player_id") is not None
    ]

    if not rows:
        logger.warning("pitcher cache refresh: no pitchers returned from API")
        return

    _upsert_cache_rows(PITCHER_CACHE_TABLE, _PITCHER_CACHE_COLUMNS, rows)
    logger.info("pitcher cache refresh: %d pitchers upserted", len(rows))


async def refresh_player_cache() -> None:
    await asyncio.gather(
        refresh_batter_cache(),
        refresh_pitcher_cache(),
    )
