# Read-only lookups for player id → (name, position, team) translation.
# Backed by player_caching, which mirrors the external API's player roster.
# Position values match the API convention (e.g., "OF" not split into LF/CF/RF).

from typing import Optional

from sqlalchemy import text as sa_text

from orm.session import engine


# 단일 선수 조회: id → (name, position, team). cache에 없으면 None.
def get_player_by_id(player_id: str) -> Optional[tuple[str, str, str]]:
    try:
        normalized_id = int(player_id)
    except (TypeError, ValueError):
        return None

    sql = sa_text("""
        SELECT name, position, team
        FROM player_caching
        WHERE player_id = :player_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"player_id": normalized_id}).fetchone()

    if not row:
        return None

    m = row._mapping
    return (m["name"], m["position"] or "", m["team"] or "")
