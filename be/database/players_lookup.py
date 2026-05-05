# Read-only lookups for player id → (name, position, team) translation.
# Backed by batter_caching and pitcher_caching, which mirror the external API roster.
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
        FROM (
            SELECT name, position, team, 0 AS priority
            FROM batter_caching
            WHERE player_id = :player_id
            UNION ALL
            SELECT name, position, team, 1 AS priority
            FROM pitcher_caching
            WHERE player_id = :player_id
        ) AS player_lookup
        ORDER BY priority
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"player_id": normalized_id}).fetchone()

    if not row:
        return None

    m = row._mapping
    return (m["name"], m["position"] or "", m["team"] or "")
