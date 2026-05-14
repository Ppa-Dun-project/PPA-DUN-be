# Batter and pitcher cache tables backed by the external PPA API.
# refresh_player_cache() pulls AL+NL batters and pitchers and upserts local cache.
import asyncio
import logging
from typing import Any

from sqlalchemy import bindparam, text

from orm.session import engine
from ppa_api.ppa_client import build_ppa_api_client

logger = logging.getLogger(__name__)


# API에서 받아오는 필드 (league는 query 필터라서 반환 컬럼이 아님 → 여기 포함 안 함)
_BATTER_API_COLUMNS = (
    "player_id", "name", "position", "team",
    "primary_number", "birth_date", "birth_city", "birth_country",
    "height", "weight", "current_age", "mlb_debut_date",
    "bat_side", "pitch_hand",
    "ab", "r", "h", "single", "double", "triple",
    "hr", "rbi", "bb", "k", "sb", "cs",
    "avg", "obp", "slg",
    "injury_status", "depth_order", "player_value",
)

_PITCHER_API_COLUMNS = (
    "player_id", "name", "position", "team",
    "w", "sv", "so", "era", "whip", "ip",
    "injury_status", "depth_order", "player_value",
    "l", "g", "gs", "war", "fip", "h", "r", "er", "hr", "bb", "hbp", "bf",
    "era_plus", "h9", "hr9", "bb9", "so9", "so_bb",
    "primary_number", "birth_date", "birth_city", "birth_country",
    "height", "weight", "current_age", "mlb_debut_date", "pitch_hand",
)

# DB 캐시 테이블에 저장하는 컬럼 = API 필드 + 우리가 태깅하는 league
_BATTER_CACHE_COLUMNS = _BATTER_API_COLUMNS + ("league",)
_PITCHER_CACHE_COLUMNS = _PITCHER_API_COLUMNS + ("league",)


def _extract_rows(response: dict[str, Any], preferred_key: str) -> list[dict[str, Any]]:
    rows = response.get(preferred_key)
    if rows is None:
        rows = response.get("players")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _upsert_cache_rows(conn, table_name: str, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
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
    conn.execute(sql, rows)


def _delete_missing_rows(conn, table_name: str, seen_ids: list[Any]) -> None:
    sql = text(f"DELETE FROM {table_name} WHERE player_id NOT IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    conn.execute(sql, {"ids": seen_ids})


def _sync_cache_table(
    *,
    label: str,
    table_name: str,
    columns: tuple[str, ...],
    rows_key: str,
    al_resp: Any,
    nl_resp: Any,
) -> None:
    # asyncio.gather(return_exceptions=True)로 받은 결과를 검사:
    # 한쪽이라도 실패면 abort. 절반만 갱신되는 잡종 상태 방지.
    if isinstance(al_resp, Exception) or isinstance(nl_resp, Exception):
        logger.error(
            "%s cache refresh aborted: AL=%r NL=%r", label, al_resp, nl_resp
        )
        return

    items = (
        [{**r, "league": "AL"} for r in _extract_rows(al_resp, rows_key)]
        + [{**r, "league": "NL"} for r in _extract_rows(nl_resp, rows_key)]
    )
    rows = [
        {col: item.get(col) for col in columns}
        for item in items
        if item.get("player_id") is not None
    ]

    if not rows:
        logger.error("%s cache refresh aborted: empty response", label)
        return

    seen_ids = [r["player_id"] for r in rows]
    # UPSERT와 stale-row DELETE를 단일 트랜잭션으로 묶음.
    # 중간 실패 시 자동 ROLLBACK으로 어제 상태 유지.
    with engine.begin() as conn:
        _upsert_cache_rows(conn, table_name, columns, rows)
        _delete_missing_rows(conn, table_name, seen_ids)

    logger.info("%s cache refresh: %d rows synced", label, len(rows))


async def refresh_batter_cache() -> None:
    client = build_ppa_api_client()
    al_resp, nl_resp = await asyncio.gather(
        client.batters_by_league("AL", columns=_BATTER_API_COLUMNS),
        client.batters_by_league("NL", columns=_BATTER_API_COLUMNS),
        return_exceptions=True,
    )
    _sync_cache_table(
        label="batter",
        table_name="batter_caching",
        columns=_BATTER_CACHE_COLUMNS,
        rows_key="batters",
        al_resp=al_resp,
        nl_resp=nl_resp,
    )


async def refresh_pitcher_cache() -> None:
    client = build_ppa_api_client()
    al_resp, nl_resp = await asyncio.gather(
        client.pitchers_by_league("AL", columns=_PITCHER_API_COLUMNS),
        client.pitchers_by_league("NL", columns=_PITCHER_API_COLUMNS),
        return_exceptions=True,
    )
    _sync_cache_table(
        label="pitcher",
        table_name="pitcher_caching",
        columns=_PITCHER_CACHE_COLUMNS,
        rows_key="pitchers",
        al_resp=al_resp,
        nl_resp=nl_resp,
    )


async def refresh_player_cache() -> None:
    await asyncio.gather(
        refresh_batter_cache(),
        refresh_pitcher_cache(),
    )
