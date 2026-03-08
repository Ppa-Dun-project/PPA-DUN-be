from typing import List, Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

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

MOCK_MY_TEAM_PLAYERS: List[MyTeamPlayerOut] = [
    MyTeamPlayerOut(
        id="p1",
        name="Shohei Ohtani",
        pos="DH",
        cost=25,
        team="LAA",
        avg=0.394,
        hr=54,
        rbi=130,
        sb=26,
        ppaValue=9.2,
    ),
    MyTeamPlayerOut(
        id="p2",
        name="Aaron Judge",
        pos="RF",
        cost=12,
        team="NYY",
        avg=0.322,
        hr=98,
        rbi=144,
        sb=3,
        ppaValue=10.6,
    ),
    MyTeamPlayerOut(
        id="p3",
        name="Juan Soto",
        pos="LF",
        cost=75,
        team="NYM",
        avg=0.288,
        hr=41,
        rbi=109,
        sb=7,
        ppaValue=7.1,
    ),
    MyTeamPlayerOut(
        id="p4",
        name="Jose Ramirez",
        pos="3B",
        cost=11,
        team="CLE",
        avg=0.279,
        hr=39,
        rbi=118,
        sb=20,
        ppaValue=7.5,
    ),
    MyTeamPlayerOut(
        id="p5",
        name="Bobby Witt Jr.",
        pos="SS",
        cost=24,
        team="KC",
        avg=0.302,
        hr=30,
        rbi=103,
        sb=49,
        ppaValue=7.0,
    ),
    MyTeamPlayerOut(
        id="p6",
        name="Zack Wheeler",
        pos="SP",
        cost=34,
        team="PHI",
        avg=0.0,
        hr=0,
        rbi=0,
        sb=0,
        ppaValue=6.2,
    ),
]

MY_TEAM_POSITIONS = [
    "ALL",
    "C",
    "1B",
    "2B",
    "3B",
    "SS",
    "LF",
    "RF",
    "CF",
    "DH",
    "SP",
    "RP",
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

TOTAL_BUDGET = 260


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


def get_budget_summary(players: List[MyTeamPlayerOut]) -> tuple[int, int, int]:
    spent = sum(p.cost for p in players)
    remaining = max(0, TOTAL_BUDGET - spent)
    return TOTAL_BUDGET, spent, remaining


# Used by MyTeamPage data table. Handles query/position/sort server-side.
@router.get("/players", response_model=MyTeamPlayersResponse)
def get_my_team_players(
    query: Optional[str] = Query(default=None),
    position: str = Query(default="ALL"),
    sort: MyTeamSort = Query(default="score_desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1),
):
    keyword = (query or "").strip().lower()
    normalized_position = position.strip().upper()

    filtered = []
    for player in MOCK_MY_TEAM_PLAYERS:
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

    total_budget, spent_budget, remaining_budget = get_budget_summary(MOCK_MY_TEAM_PLAYERS)
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
def get_my_team_summary():
    total_budget, spent_budget, remaining_budget = get_budget_summary(MOCK_MY_TEAM_PLAYERS)
    return MyTeamSummaryResponse(
        totalBudget=total_budget,
        spentBudget=spent_budget,
        remainingBudget=remaining_budget,
        playerCount=len(MOCK_MY_TEAM_PLAYERS),
    )
