# Players page API router.
# Provides player detail views from batter_caching or pitcher_caching.
import logging
import re
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from orm.session import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/players", tags=["players"])

PlayerType = Literal["batter", "pitcher"]


class BatterStats(BaseModel):
    avg: float = 0.0
    pa: int = 0
    hr: int = 0
    ops: float = 0.0
    rbi: int = 0
    ab: int = 0
    r: int = 0
    h: int = 0
    bb: int = 0
    k: int = 0
    sb: int = 0
    cs: int = 0
    obp: float = 0.0
    slg: float = 0.0


class PitcherStats(BaseModel):
    w: int = 0
    sv: int = 0
    so: int = 0
    era: float = 0.0
    whip: float = 0.0
    ip: float = 0.0
    l: int = 0
    g: int = 0
    gs: int = 0
    war: float = 0.0
    fip: float = 0.0
    h: int = 0
    r: int = 0
    er: int = 0
    hr: int = 0
    bb: int = 0
    hbp: int = 0
    bf: int = 0
    era_plus: int = 0
    h9: float = 0.0
    hr9: float = 0.0
    bb9: float = 0.0
    so9: float = 0.0
    so_bb: float = 0.0


class PlayerOut(BaseModel):
    id: int
    playerType: PlayerType
    name: str
    age: int
    height_in: int
    weight_lb: int
    bats: Optional[str] = None
    throws: str
    team: str
    positions: list[str]
    valueScore: float
    headshotUrl: Optional[str] = None
    batterStats: Optional[BatterStats] = None
    pitcherStats: Optional[PitcherStats] = None


def parse_height_to_inches(height_str: str | None) -> int:
    match = re.match(r"(\d+)'\s*(\d+)\"?", height_str or "")
    if match:
        return int(match.group(1)) * 12 + int(match.group(2))
    return 0


def headshot_url(player_id: int) -> str:
    return (
        "https://img.mlbstatic.com/mlb-photos/image/upload/"
        "d_people:generic:headshot:67:current.png/"
        f"w_213,q_auto:best/v1/people/{player_id}/headshot/67/current"
    )


def int_value(value) -> int:
    return int(value or 0)


def float_value(value, digits: int = 3) -> float:
    return round(float(value or 0.0), digits)


def build_batter_detail(player_id: int) -> PlayerOut:
    sql = text("""
        SELECT player_id, name, position, team,
               current_age, height, weight, bat_side, pitch_hand,
               ab, r, h, hr, rbi, bb, k, sb, cs,
               avg, obp, slg, player_value, depth_order
        FROM batter_caching
        WHERE player_id = :player_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"player_id": player_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Batter not found")

    m = row._mapping
    ab = int_value(m["ab"])
    bb = int_value(m["bb"])
    obp = float_value(m["obp"])
    slg = float_value(m["slg"])

    return PlayerOut(
        id=m["player_id"],
        playerType="batter",
        name=m["name"] or "",
        age=int_value(m["current_age"]),
        height_in=parse_height_to_inches(m["height"]),
        weight_lb=int_value(m["weight"]),
        bats=m["bat_side"] or "R",
        throws=m["pitch_hand"] or "R",
        team=m["team"] or "",
        positions=[m["position"] or "DH"],
        valueScore=float_value(m["player_value"]),
        headshotUrl=headshot_url(m["player_id"]),
        batterStats=BatterStats(
            avg=float_value(m["avg"]),
            pa=ab + bb,
            hr=int_value(m["hr"]),
            ops=round(obp + slg, 3),
            rbi=int_value(m["rbi"]),
            ab=ab,
            r=int_value(m["r"]),
            h=int_value(m["h"]),
            bb=bb,
            k=int_value(m["k"]),
            sb=int_value(m["sb"]),
            cs=int_value(m["cs"]),
            obp=obp,
            slg=slg,
            depth_order=int_value(m["depth_order"])
        ),
    )


def build_pitcher_detail(player_id: int) -> PlayerOut:
    sql = text("""
        SELECT player_id, name, position, team,
               current_age, height, weight, pitch_hand, player_value,
               w, sv, so, era, whip, ip,
               l, g, gs, war, fip, h, r, er, hr, bb, hbp, bf,
               era_plus, h9, hr9, bb9, so9, so_bb, depth_order
        FROM pitcher_caching
        WHERE player_id = :player_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"player_id": player_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Pitcher not found")

    m = row._mapping
    return PlayerOut(
        id=m["player_id"],
        playerType="pitcher",
        name=m["name"] or "",
        age=int_value(m["current_age"]),
        height_in=parse_height_to_inches(m["height"]),
        weight_lb=int_value(m["weight"]),
        bats=None,
        throws=m["pitch_hand"] or "R",
        team=m["team"] or "",
        positions=[m["position"] or "P"],
        valueScore=float_value(m["player_value"]),
        headshotUrl=headshot_url(m["player_id"]),
        pitcherStats=PitcherStats(
            w=int_value(m["w"]),
            sv=int_value(m["sv"]),
            so=int_value(m["so"]),
            era=float_value(m["era"], 2),
            whip=float_value(m["whip"], 3),
            ip=float_value(m["ip"], 1),
            l=int_value(m["l"]),
            g=int_value(m["g"]),
            gs=int_value(m["gs"]),
            war=float_value(m["war"]),
            fip=float_value(m["fip"], 2),
            h=int_value(m["h"]),
            r=int_value(m["r"]),
            er=int_value(m["er"]),
            hr=int_value(m["hr"]),
            bb=int_value(m["bb"]),
            hbp=int_value(m["hbp"]),
            bf=int_value(m["bf"]),
            era_plus=int_value(m["era_plus"]),
            h9=float_value(m["h9"], 2),
            hr9=float_value(m["hr9"], 2),
            bb9=float_value(m["bb9"], 2),
            so9=float_value(m["so9"], 2),
            so_bb=float_value(m["so_bb"], 2),
            depth_order=int_value(m["depth_order"]),
        ),
    )


@router.get("/{player_id}", response_model=PlayerOut)
def get_player_detail(
    player_id: int,
    playerType: PlayerType = Query("batter"),
):
    if playerType == "pitcher":
        return build_pitcher_detail(player_id)
    return build_batter_detail(player_id)
