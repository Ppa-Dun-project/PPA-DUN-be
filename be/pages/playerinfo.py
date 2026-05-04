# Players page API router.
# Provides player detail with full stats and a per-player value endpoint.
# All data is read from the player_caching table.
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from orm.session import engine

logger = logging.getLogger(__name__)

# Used by Player pages. This router owns player list/detail/filter APIs.
router = APIRouter(prefix="/api/players", tags=["players"])


# Used by PlayerDetail page. Detailed stat block for a single player.
class PlayerStats(BaseModel):
    g: int              # 경기 수
    pa: int             # 타석 수
    hr: int             # 홈런 수
    ops: float          # OPS (출루율 + 장타율)
    ip: float = 0.0     # 투구 이닝 (투수인 경우)
    
    # Additional batting stats
    ab: int = 0         # 타수
    r: int = 0          # 득점
    h: int = 0          # 안타
    rbi: int = 0        # 타점
    bb: int = 0         # 볼넷
    k: int = 0          # 삼진
    sb: int = 0         # 도루
    cs: int = 0         # 도루 실패 (Caught Stealing)
    avg: float = 0.0    # 타율
    obp: float = 0.0    # 출루율
    slg: float = 0.0    # 장타율

# Used by PlayerDetail page. Full data for a single player.
class PlayerOut(BaseModel):
    id: int
    name: str
    age: int
    height_in: int
    weight_lb: int
    bats: str
    throws: str
    team: str
    positions: List[str]
    valueScore: float
    headshotUrl: Optional[str] = None
    stats: PlayerStats


# Used by HomePage Injured Players strip + "View All" popup.
class InjuredPlayer(BaseModel):
    player_id: int
    name: str
    position: Optional[str] = None
    team: Optional[str] = None
    primary_number: Optional[str] = None
    injury_status: str
    player_value: Optional[float] = None


def parse_height_to_inches(height_str: str) -> int:
    match = re.match(r"(\d+)'\s*(\d+)\"?", height_str or "")
    if match:
        return int(match.group(1)) * 12 + int(match.group(2))
    return 0


# Currently injured players, sorted by player_value desc.
# - Strip on HomePage uses ?limit=3
# - "View All" popup omits limit → returns full list
# - Defined BEFORE /{player_id} so the literal "/injured" path matches first.
@router.get("/injured", response_model=List[InjuredPlayer])
def list_injured(limit: Optional[int] = None):
    sql = (
        "SELECT player_id, name, position, team, primary_number, "
        "       injury_status, player_value "
        "FROM player_caching "
        "WHERE injury_status IS NOT NULL "
        "ORDER BY player_value DESC"
    )
    params: dict = {}
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    return [
        InjuredPlayer(
            player_id=r._mapping["player_id"],
            name=r._mapping["name"],
            position=r._mapping["position"],
            team=r._mapping["team"],
            primary_number=r._mapping["primary_number"],
            injury_status=r._mapping["injury_status"],
            player_value=(
                float(r._mapping["player_value"])
                if r._mapping["player_value"] is not None
                else None
            ),
        )
        for r in rows
    ]


# player_caching 테이블에서 선수의 personal info + 통합 스탯 + value를 단일 쿼리로 조회.
@router.get("/{player_id}", response_model=PlayerOut)
def get_player_detail(player_id: int):
    sql = text("""
        SELECT player_id, name, position, team,
               current_age, height, weight, bat_side, pitch_hand,
               ab, r, h, hr, rbi, bb, k, sb, cs,
               avg, obp, slg, player_value
        FROM player_caching
        WHERE player_id = :player_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"player_id": player_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Player not found")

    m = row._mapping
    ab = m["ab"] or 0
    bb = m["bb"] or 0
    obp = m["obp"] or 0.0
    slg = m["slg"] or 0.0

    return PlayerOut(
        id=m["player_id"],
        name=m["name"],
        age=m["current_age"] or 0,
        height_in=parse_height_to_inches(m["height"]),
        weight_lb=m["weight"] or 0,
        bats=m["bat_side"] or "R",
        throws=m["pitch_hand"] or "R",
        team=m["team"] or "",
        positions=[m["position"] or "DH"],
        valueScore=float(m["player_value"] or 0.0),
        headshotUrl=f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{m['player_id']}/headshot/67/current",
        stats=PlayerStats(
            g=0,
            pa=ab + bb,
            hr=m["hr"] or 0,
            ops=round(obp + slg, 3),
            ip=0.0,
            ab=ab,
            r=m["r"] or 0,
            h=m["h"] or 0,
            rbi=m["rbi"] or 0,
            bb=bb,
            k=m["k"] or 0,
            sb=m["sb"] or 0,
            cs=m["cs"] or 0,
            avg=round(float(m["avg"] or 0.0), 3),
            obp=round(float(obp), 3),
            slg=round(float(slg), 3),
        ),
    )

