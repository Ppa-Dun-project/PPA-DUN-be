# Player cache table backed by the external API GET /players endpoint.
# refresh_player_cache() pulls the AL+NL rosters and upserts into player_caching.
# Scheduled daily by APScheduler in main.py; no manual trigger endpoint.
import asyncio
import logging

from sqlalchemy import (
    Column, Float, Integer, MetaData, String, Table,
    inspect, text,
)

from orm.session import engine
from ppa_api.ppa_client import build_ppa_api_client

logger = logging.getLogger(__name__)

# 외부 API GET /players 응답에서 받아 cache 테이블에 저장할 컬럼들.
# 순서가 INSERT placeholder 와 매칭되므로 변경 시 양쪽 같이 업데이트.
_CACHE_COLUMNS = (
    "player_id", "name", "position", "team",
    "primary_number", "birth_date", "birth_city", "birth_country",
    "height", "weight", "current_age", "mlb_debut_date",
    "bat_side", "pitch_hand",
    "ab", "r", "h", "single", "double", "triple",
    "hr", "rbi", "bb", "k", "sb", "cs",
    "avg", "obp", "slg",
    "injury_status", "depth_order", "player_value",
)


def ensure_player_cache_table() -> None:
    inspector = inspect(engine)
    if inspector.has_table("player_caching"):
        return

    metadata = MetaData()
    Table(
        "player_caching", metadata,
        Column("player_id", Integer, primary_key=True),
        Column("name", String(100)),
        Column("position", String(10)),
        Column("team", String(10)),
        Column("primary_number", String(10)),
        Column("birth_date", String(20)),
        Column("birth_city", String(100)),
        Column("birth_country", String(100)),
        Column("height", String(20)),
        Column("weight", Integer),
        Column("current_age", Integer),
        Column("mlb_debut_date", String(20)),
        Column("bat_side", String(5)),
        Column("pitch_hand", String(5)),
        Column("ab", Integer),
        Column("r", Integer),
        Column("h", Integer),
        Column("single", Integer),
        Column("double", Integer),
        Column("triple", Integer),
        Column("hr", Integer),
        Column("rbi", Integer),
        Column("bb", Integer),
        Column("k", Integer),
        Column("sb", Integer),
        Column("cs", Integer),
        Column("avg", Float),
        Column("obp", Float),
        Column("slg", Float),
        Column("injury_status", String(50)),
        Column("depth_order", Integer),
        Column("player_value", Float),
    )
    metadata.create_all(engine)
    print("Table created: player_caching")


# AL/NL 전체 선수 목록을 외부 API에서 받아 player_caching 테이블에 UPSERT.
# 실패 시 로그만 남기고 기존 cache 유지 (다음 스케줄 때 재시도). API 응답에 사라진
# 선수도 cache에는 그대로 남음 (stale 허용).
async def refresh_player_cache() -> None:
    client = build_ppa_api_client()
    try:
        al_resp, nl_resp = await asyncio.gather(
            client.players_by_league("AL", columns=_CACHE_COLUMNS),
            client.players_by_league("NL", columns=_CACHE_COLUMNS),
        )
    except Exception as exc:
        logger.warning("player cache refresh failed: %s", exc)
        return

    players = (al_resp.get("players") or []) + (nl_resp.get("players") or [])
    rows = [
        {col: p.get(col) for col in _CACHE_COLUMNS}
        for p in players
        if p.get("player_id") is not None
    ]

    if not rows:
        logger.warning("player cache refresh: no players returned from API")
        return

    # MariaDB/MySQL 예약어 (예: double) 가 컬럼명에 포함되어 있으므로 모든 컬럼명을 backtick으로 감쌈.
    quoted_cols = ", ".join(f"`{c}`" for c in _CACHE_COLUMNS)
    placeholders = ", ".join(f":{c}" for c in _CACHE_COLUMNS)
    update_clause = ", ".join(
        f"`{c}` = VALUES(`{c}`)" for c in _CACHE_COLUMNS if c != "player_id"
    )
    sql = text(f"""
        INSERT INTO player_caching ({quoted_cols})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """)

    with engine.begin() as conn:
        conn.execute(sql, rows)

    logger.info("player cache refresh: %d players upserted", len(rows))
