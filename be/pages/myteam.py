# My Team page API router.
# Returns the selected draft session's roster and budget summary.
# Filtering, sorting, and pagination are handled by the frontend.
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import bindparam, text as sa_text

from database.draft_store import load_draft_config
from orm.session import engine
from pages.draft import _verify_session_owner, get_session_picks
from security import get_user_id

router = APIRouter(prefix="/api/my-team", tags=["my-team"])


class MyTeamPlayerOut(BaseModel):
    id: str
    name: str
    pos: str
    cost: int
    team: str
    avg: float
    hr: int
    rbi: int
    sb: int
    ppaValue: float


class MyTeamPlayersResponse(BaseModel):
    items: List[MyTeamPlayerOut]
    totalBudget: int
    spentBudget: int
    remainingBudget: int


def pick_my_players(session_id: int) -> List[MyTeamPlayerOut]:
    # Load the session's picks, then enrich only my roster rows from player_caching.
    picks = get_session_picks(session_id)
    mine = sorted(
        (pick for pick in picks if pick.draftedByTeamId == "team-0"),
        key=lambda pick: pick.slotIndex,
    )

    if not mine:
        return []

    player_ids = [int(pick.playerId) for pick in mine]
    sql = sa_text("""
        SELECT player_id, position, team, avg, hr, rbi, sb, player_value, name
        FROM player_caching
        WHERE player_id IN :ids
    """).bindparams(bindparam("ids", expanding=True))

    with engine.connect() as conn:
        rows = conn.execute(sql, {"ids": player_ids}).fetchall()

    cache_by_id = {row._mapping["player_id"]: row._mapping for row in rows}

    items: List[MyTeamPlayerOut] = []
    for pick in mine:
        player = cache_by_id.get(int(pick.playerId))
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
                pos=display_pos,
                cost=int(pick.bid or 0),
                team=player["team"] or "",
                avg=float(player["avg"] or 0.0),
                hr=int(player["hr"] or 0),
                rbi=int(player["rbi"] or 0),
                sb=int(player["sb"] or 0),
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
