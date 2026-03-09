from typing import List, Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from draft import DEFAULT_DRAFT_CONFIG, find_draft_player, get_room_picks

# Used by My Team page data requests.
router = APIRouter(prefix="/api/my-team", tags=["my-team"])


# Used by My Team table rows.
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
    page: int
    limit: int
    total: int
    totalPages: int
    totalBudget: int
    spentBudget: int
    remainingBudget: int


class MyTeamPositionsResponse(BaseModel):
    positions: List[str]


class MyTeamSortOption(BaseModel):
    value: str
    label: str


class MyTeamSortOptionsResponse(BaseModel):
    sorts: List[MyTeamSortOption]


class MyTeamSummaryResponse(BaseModel):
    totalBudget: int
    spentBudget: int
    remainingBudget: int
    playerCount: int


MyTeamSort = Literal[
    "score_desc",
    "score_asc",
    "cost_desc",
    "cost_asc",
    "avg_desc",
    "hr_desc",
    "rbi_desc",
    "sb_desc",
]

MY_TEAM_POSITIONS = [
    "ALL",
    "C",
    "1B",
    "2B",
    "3B",
    "SS",
    "OF",
    "UTIL",
    "SP",
    "RP",
    "LF",
    "RF",
    "CF",
    "DH",
]

MY_TEAM_SORT_OPTIONS: List[MyTeamSortOption] = [
    MyTeamSortOption(value="score_desc", label="By Score (desc)"),
    MyTeamSortOption(value="score_asc", label="By Score (asc)"),
    MyTeamSortOption(value="cost_desc", label="By Value $ (desc)"),
    MyTeamSortOption(value="cost_asc", label="By Value $ (asc)"),
    MyTeamSortOption(value="avg_desc", label="By AVG"),
    MyTeamSortOption(value="hr_desc", label="By HR"),
    MyTeamSortOption(value="rbi_desc", label="By RBI"),
    MyTeamSortOption(value="sb_desc", label="By SB"),
]

def draft_pick_to_my_team_player(player_id: str, slot_pos: str, bid: Optional[int]) -> Optional[MyTeamPlayerOut]:
    draft_player = find_draft_player(player_id)
    if not draft_player:
        return None

    if slot_pos == "BENCH":
        position = draft_player.positions[0] if draft_player.positions else "UTIL"
    else:
        position = slot_pos

    resolved_cost = bid if isinstance(bid, int) else draft_player.recommendedBid

    return MyTeamPlayerOut(
        id=draft_player.id,
        name=draft_player.name,
        pos=position,
        cost=max(0, int(resolved_cost)),
        team=draft_player.team,
        avg=float(draft_player.avg or 0.0),
        hr=int(draft_player.hr or 0),
        rbi=int(draft_player.rbi or 0),
        sb=int(draft_player.sb or 0),
        ppaValue=float(draft_player.ppaValue),
    )


def build_my_team_players(room_id: str, my_team_id: str) -> List[MyTeamPlayerOut]:
    picks = get_room_picks(room_id)
    mine = sorted(
        (pick for pick in picks if pick.draftedByTeamId == my_team_id),
        key=lambda pick: pick.slotIndex,
    )

    items: List[MyTeamPlayerOut] = []
    for pick in mine:
        mapped = draft_pick_to_my_team_player(
            player_id=pick.playerId,
            slot_pos=pick.slotPos,
            bid=pick.bid,
        )
        if mapped:
            items.append(mapped)
    return items


def sort_my_team(players: List[MyTeamPlayerOut], sort: MyTeamSort) -> List[MyTeamPlayerOut]:
    if sort == "score_desc":
        return sorted(players, key=lambda p: p.ppaValue, reverse=True)
    if sort == "score_asc":
        return sorted(players, key=lambda p: p.ppaValue)
    if sort == "cost_desc":
        return sorted(players, key=lambda p: p.cost, reverse=True)
    if sort == "cost_asc":
        return sorted(players, key=lambda p: p.cost)
    if sort == "avg_desc":
        return sorted(players, key=lambda p: p.avg, reverse=True)
    if sort == "hr_desc":
        return sorted(players, key=lambda p: p.hr, reverse=True)
    if sort == "rbi_desc":
        return sorted(players, key=lambda p: p.rbi, reverse=True)
    if sort == "sb_desc":
        return sorted(players, key=lambda p: p.sb, reverse=True)
    return players


def get_budget_summary(players: List[MyTeamPlayerOut], total_budget: int) -> tuple[int, int, int]:
    spent = sum(p.cost for p in players)
    remaining = max(0, total_budget - spent)
    return total_budget, spent, remaining


# Used by MyTeamPage data table. Handles query/position/sort server-side.
@router.get("/players", response_model=MyTeamPlayersResponse)
def get_my_team_players(
    query: Optional[str] = Query(default=None),
    position: str = Query(default="ALL"),
    sort: MyTeamSort = Query(default="score_desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1),
    room_id: str = Query(default="default", alias="roomId"),
    my_team_id: str = Query(default="team-me", alias="myTeamId"),
):
    source_players = build_my_team_players(room_id=room_id, my_team_id=my_team_id)
    keyword = (query or "").strip().lower()
    normalized_position = position.strip().upper()

    filtered = []
    for player in source_players:
        matches_keyword = (
            not keyword
            or keyword in player.name.lower()
            or keyword in player.team.lower()
        )
        matches_position = normalized_position == "ALL" or player.pos.upper() == normalized_position
        if matches_keyword and matches_position:
            filtered.append(player)

    sorted_players = sort_my_team(filtered, sort)
    total = len(sorted_players)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    safe_page = min(page, total_pages) if total_pages > 0 else 1
    start = (safe_page - 1) * limit if total_pages > 0 else 0
    end = start + limit
    paged = sorted_players[start:end]

    total_budget, spent_budget, remaining_budget = get_budget_summary(
        source_players,
        DEFAULT_DRAFT_CONFIG.budget,
    )
    return MyTeamPlayersResponse(
        items=paged,
        page=safe_page,
        limit=limit,
        total=total,
        totalPages=total_pages,
        totalBudget=total_budget,
        spentBudget=spent_budget,
        remainingBudget=remaining_budget,
    )


# Used by MyTeamPage position chips.
@router.get("/filters/positions", response_model=MyTeamPositionsResponse)
def get_my_team_position_filters():
    return MyTeamPositionsResponse(positions=MY_TEAM_POSITIONS)


# Used by MyTeamPage sort dropdown.
@router.get("/filters/sorts", response_model=MyTeamSortOptionsResponse)
def get_my_team_sort_options():
    return MyTeamSortOptionsResponse(sorts=MY_TEAM_SORT_OPTIONS)


# Used by MyTeamPage budget widget.
@router.get("/summary", response_model=MyTeamSummaryResponse)
def get_my_team_summary(
    room_id: str = Query(default="default", alias="roomId"),
    my_team_id: str = Query(default="team-me", alias="myTeamId"),
):
    source_players = build_my_team_players(room_id=room_id, my_team_id=my_team_id)
    total_budget, spent_budget, remaining_budget = get_budget_summary(
        source_players,
        DEFAULT_DRAFT_CONFIG.budget,
    )
    return MyTeamSummaryResponse(
        totalBudget=total_budget,
        spentBudget=spent_budget,
        remainingBudget=remaining_budget,
        playerCount=len(source_players),
    )
