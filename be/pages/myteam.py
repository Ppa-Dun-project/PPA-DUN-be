# My Team page API router.
# Returns the selected draft session's roster and budget summary.
# Filtering, sorting, and pagination are handled by the frontend.
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import bindparam, text as sa_text

from database.draft_store import load_draft_config
from orm.session import engine
from pages.draft import _verify_session_owner, get_session_picks
from security import get_user_id

router = APIRouter(prefix="/api/my-team", tags=["my-team"])

PlayerType = Literal["batter", "pitcher"]


class MyTeamPlayerOut(BaseModel):
    id: str
    name: str
    playerType: PlayerType
    pos: str
    cost: int
    team: str
    avg: float
    hr: int
    rbi: int
    sb: int
    w: Optional[int] = None
    sv: Optional[int] = None
    so: Optional[int] = None
    era: Optional[float] = None
    whip: Optional[float] = None
    ip: Optional[float] = None
    ppaValue: float


class MyTeamPlayersResponse(BaseModel):
    items: List[MyTeamPlayerOut]
    totalBudget: int
    spentBudget: int
    remainingBudget: int


def pick_my_players(session_id: int) -> List[MyTeamPlayerOut]:
    # Load the session's picks, then enrich my roster rows from batter/pitcher caches.
    picks = get_session_picks(session_id)
    mine = sorted(
        (pick for pick in picks if pick.draftedByTeamId == "team-0"),
        key=lambda pick: pick.slotIndex,
    )

    if not mine:
        return []

    player_ids = [int(pick.playerId) for pick in mine]
    batter_sql = sa_text("""
        SELECT player_id, position, team, avg, hr, rbi, sb, player_value, name
        FROM batter_caching
        WHERE player_id IN :ids
    """).bindparams(bindparam("ids", expanding=True))
    pitcher_sql = sa_text("""
        SELECT player_id, position, team, w, sv, so, era, whip, ip, player_value, name
        FROM pitcher_caching
        WHERE player_id IN :ids
    """).bindparams(bindparam("ids", expanding=True))

    with engine.connect() as conn:
        batter_rows = conn.execute(batter_sql, {"ids": player_ids}).fetchall()
        pitcher_rows = conn.execute(pitcher_sql, {"ids": player_ids}).fetchall()

    batters_by_id = {row._mapping["player_id"]: row._mapping for row in batter_rows}
    pitchers_by_id = {row._mapping["player_id"]: row._mapping for row in pitcher_rows}

    items: List[MyTeamPlayerOut] = []
    for pick in mine:
        normalized_id = int(pick.playerId)
        wants_pitcher = pick.slotPos in ("SP", "RP")
        player_type: PlayerType = "pitcher" if wants_pitcher and normalized_id in pitchers_by_id else "batter"
        player = pitchers_by_id.get(normalized_id) if player_type == "pitcher" else batters_by_id.get(normalized_id)
        if not player and player_type == "batter":
            player_type = "pitcher"
            player = pitchers_by_id.get(normalized_id)
        elif not player:
            player_type = "batter"
            player = batters_by_id.get(normalized_id)

        if not player:
            continue

        if pick.slotPos == "BENCH":
            raw_pos = player["position"] or "UTIL"
            original_pos = "UTIL" if raw_pos in ("DH", "TWP") else raw_pos
            display_pos = f"BENCH({original_pos})"
        else:
            display_pos = pick.slotPos

        items.append(
            MyTeamPlayerOut(
                id=str(player["player_id"]),
                name=player["name"],
                playerType=player_type,
                pos=display_pos,
                cost=int(pick.bid or 0),
                team=player["team"] or "",
                avg=float(player["avg"] or 0.0) if player_type == "batter" else 0.0,
                hr=int(player["hr"] or 0) if player_type == "batter" else 0,
                rbi=int(player["rbi"] or 0) if player_type == "batter" else 0,
                sb=int(player["sb"] or 0) if player_type == "batter" else 0,
                w=int(player["w"] or 0) if player_type == "pitcher" else None,
                sv=int(player["sv"] or 0) if player_type == "pitcher" else None,
                so=int(player["so"] or 0) if player_type == "pitcher" else None,
                era=round(float(player["era"] or 0.0), 2) if player_type == "pitcher" else None,
                whip=round(float(player["whip"] or 0.0), 3) if player_type == "pitcher" else None,
                ip=round(float(player["ip"] or 0.0), 1) if player_type == "pitcher" else None,
                ppaValue=float(player["player_value"] or 0.0),
            )
        )

    return items


def get_budget_summary(players: List[MyTeamPlayerOut], total_budget: int) -> tuple[int, int, int]:
    spent = sum(player.cost for player in players)
    remaining = max(0, total_budget - spent)
    return total_budget, spent, remaining


@router.get("/players", response_model=MyTeamPlayersResponse)
def get_my_team_players(
    session_id: int = Query(..., alias="sessionId", gt=0),
    current_user_id: int = Depends(get_user_id),
):
    user_id = str(current_user_id)
    _verify_session_owner(session_id, user_id)

    source_players = pick_my_players(session_id=session_id)

    config = load_draft_config(session_id)
    budget = config["budget"] if config else 0

    total_budget, spent_budget, remaining_budget = get_budget_summary(
        source_players,
        budget,
    )

    return MyTeamPlayersResponse(
        items=source_players,
        totalBudget=total_budget,
        spentBudget=spent_budget,
        remainingBudget=remaining_budget,
    )
