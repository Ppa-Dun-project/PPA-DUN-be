# Read-only lookups for player id ↔ (name, position, team) translation.
# Bridges between our system's player_id and the external API's name+position
# identifier convention. Backed by mlb_players_list as a transitional source —
# when a caching DB synced from the external API replaces it, only the SQL
# changes; the function signatures stay the same.

from typing import Optional

from sqlalchemy import text as sa_text

from database.draft_store import engine


# DB는 LF/CF/RF로 세분 저장하지만 외부 API는 통합된 "OF" 사용.
_POSITION_NORMALIZATION = {
    "LF": "OF",
    "CF": "OF",
    "RF": "OF",
}


def _normalize_position(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return _POSITION_NORMALIZATION.get(raw, raw)


# 단일 선수 조회: id → (name, position, team). 없으면 None.
def get_player_by_id(player_id: str) -> Optional[tuple[str, str, str]]:
    try:
        normalized_id = int(player_id)
    except (TypeError, ValueError):
        return None

    sql = sa_text("""
        SELECT p.full_name, p.position, t.abbreviation
        FROM mlb_players_list p
        LEFT JOIN mlb_team_list t ON p.team_id = t.team_id
        WHERE p.active = 1 AND p.player_id = :player_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"player_id": normalized_id}).fetchone()

    if not row:
        return None

    m = row._mapping
    return (
        m["full_name"],
        _normalize_position(m["position"]),
        m["abbreviation"] or "",
    )


