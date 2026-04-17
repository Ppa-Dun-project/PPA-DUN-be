# Players page API router.
# Provides player list with search/filter/sort, player detail with full stats,
# and a per-player value endpoint that reads from the player_ppa_scores table.
# Used when the user browses the Players catalog or opens a player detail modal.
import logging
import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
engine = create_engine(DATABASE_URL)

logger = logging.getLogger(__name__)

# Used by Player pages. This router owns player list/detail/filter APIs.
router = APIRouter(prefix="/api/players", tags=["players"])


# Used by PlayerDetail page. Detailed stat block for a single player.
class PlayerStats(BaseModel):
    g: int
    pa: int
    hr: int
    ops: float
    ip: float = 0.0
    # Additional batting stats
    ab: int = 0
    r: int = 0
    h: int = 0
    rbi: int = 0
    bb: int = 0
    k: int = 0
    sb: int = 0
    avg: float = 0.0
    obp: float = 0.0
    slg: float = 0.0

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

# DB position -> UI filter mapping (LF, CF, RF -> OF)
POSITION_TO_FILTER = {
    "LF": "OF", "CF": "OF", "RF": "OF",
    "TWP": "P", "IF": "SS",
}


def parse_height_to_inches(height_str: str) -> int:
    """Converts height string like 6' 0\" to total inches."""
    match = re.match(r"(\d+)'\s*(\d+)\"?", height_str or "")
    if match:
        return int(match.group(1)) * 12 + int(match.group(2))
    return 0


def row_to_player_out(row) -> PlayerOut:
    """Converts a DB row into a PlayerOut model with full stats."""
    r = row._mapping
    raw_pos = r["position"] or "DH"
    display_pos = POSITION_TO_FILTER.get(raw_pos, raw_pos)

    ab = r.get("AB") or 0
    bb = r.get("BB") or 0
    hr = r.get("HR") or 0
    obp = r.get("OBP") or 0.0
    slg = r.get("SLG") or 0.0

    return PlayerOut(
        id=r["player_id"],
        name=r["full_name"],
        age=r["current_age"] or 0,
        height_in=parse_height_to_inches(r["height"]),
        weight_lb=r["weight"] or 0,
        bats=r["bat_side"] or "R",
        throws=r["pitch_hand"] or "R",
        team=r["abbreviation"] or "",
        positions=[display_pos],
        valueScore=0,
        headshotUrl=f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{r['player_id']}/headshot/67/current",
        stats=PlayerStats(
            g=0,
            pa=ab + bb,
            hr=hr,
            ops=round(obp + slg, 3),
            ip=0.0,
            ab=ab,
            r=r.get("R") or 0,
            h=r.get("H") or 0,
            rbi=r.get("RBI") or 0,
            bb=bb,
            k=r.get("K") or 0,
            sb=r.get("SB") or 0,
            avg=round(float(r.get("AVG") or 0), 3),
            obp=round(float(obp), 3),
            slg=round(float(slg), 3),
        ),
    )


# Base JOIN query (players + teams + stats + PPA scores)
BASE_QUERY = """
    FROM mlb_players_list p
    LEFT JOIN mlb_team_list t ON p.team_id = t.team_id
    LEFT JOIN players_stats_nl_2025 s ON LOWER(s.Player) LIKE CONCAT(LOWER(p.full_name), ' %')
    WHERE p.active = 1
"""

# Detail SELECT (full stats)
DETAIL_SELECT = """
    SELECT p.*, t.abbreviation,
           s.AB, s.R, s.H, s.HR, s.RBI, s.BB, s.K, s.SB,
           s.AVG, s.OBP, s.SLG
"""


# Used by PlayerDetail page.
@router.get("/{player_id}", response_model=PlayerOut)
def get_player_detail(player_id: int):
    detail_sql = f"""
        {DETAIL_SELECT}
        {BASE_QUERY} AND p.player_id = :player_id
    """
    with engine.connect() as conn:
        row = conn.execute(text(detail_sql), {"player_id": player_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Player not found")

    return row_to_player_out(row)


# Value endpoint called by the frontend PlayerInfoModal.
# TODO: replace with real-time PPA API call
class PlayerValueResponse(BaseModel):
    playerId: int
    name: str
    valueScore: float


@router.get("/{player_id}/value", response_model=PlayerValueResponse)
def get_player_value(player_id: int):
    return PlayerValueResponse(
        playerId=player_id,
        name="",
        valueScore=0,
    )
