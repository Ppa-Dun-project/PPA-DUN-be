from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Used by Draft page APIs (config/filters/teams/players/picks).
router = APIRouter(prefix="/api/draft", tags=["draft"])

DraftPosition = Literal["C", "1B", "2B", "3B", "SS", "OF", "UTIL", "SP", "RP", "BENCH"]
DraftPositionFilter = Literal["ALL", "C", "1B", "2B", "3B", "SS", "OF", "UTIL", "SP", "RP"]
DraftSort = Literal[
    "score_desc",
    "score_asc",
    "cost_desc",
    "cost_asc",
    "avg_desc",
    "hr_desc",
    "rbi_desc",
    "sb_desc",
]
DraftPickType = Literal["mine", "taken"]


# Used by DraftSetup/Draft page. Represents normalized draft config.
class DraftConfigOut(BaseModel):
    leagueType: str
    budget: int
    rosterPlayers: int
    myTeamName: str
    oppTeamName: str
    opponentsCount: int
    oppTeamNames: List[str]

class DraftTeamOut(BaseModel):
    id: str
    name: str
    isMine: bool

class DraftPlayerOut(BaseModel):
    id: str
    name: str
    positions: List[DraftPosition]
    recommendedBid: int
    team: str
    avg: Optional[float] = None
    hr: Optional[int] = None
    rbi: Optional[int] = None
    sb: Optional[int] = None
    ppaValue: float

class DraftPlayerListResponse(BaseModel):
    items: List[DraftPlayerOut]
    page: int
    limit: int
    total: int
    totalPages: int

class DraftSortOption(BaseModel):
    value: str
    label: str

class DraftPositionFiltersResponse(BaseModel):
    positions: List[str]

class DraftSortFiltersResponse(BaseModel):
    sorts: List[DraftSortOption]

class DraftTeamsResponse(BaseModel):
    items: List[DraftTeamOut]

class DraftPickOut(BaseModel):
    playerId: str
    draftedByTeamId: str
    slotIndex: int
    slotPos: DraftPosition
    bid: Optional[int] = None
    type: DraftPickType

class DraftPickUpsertIn(BaseModel):
    playerId: str
    draftedByTeamId: str
    slotPos: DraftPosition
    bid: Optional[int] = None
    type: DraftPickType
    # Deprecated from frontend. Server now resolves slot index.
    slotIndex: Optional[int] = None

class DraftAllowedPositionsResponse(BaseModel):
    roomId: str
    teamId: str
    playerId: str
    allowedPositions: List[DraftPosition]
    defaultSelectedPos: Optional[DraftPosition] = None

class DraftPicksResponse(BaseModel):
    roomId: str
    items: List[DraftPickOut]

class DraftBootstrapResponse(BaseModel):
    config: DraftConfigOut
    teams: List[DraftTeamOut]
    positionFilters: List[str]
    sortOptions: List[DraftSortOption]
    picks: List[DraftPickOut]


# Draft mock source (later replace with DB tables).
MOCK_DRAFT_PLAYERS: List[DraftPlayerOut] = [
    DraftPlayerOut(id="1", name="Shohei Ohtani", positions=["UTIL"], recommendedBid=52, team="LAD", avg=0.304, hr=44, rbi=95, sb=28, ppaValue=99.2),
    DraftPlayerOut(id="2", name="Mookie Betts", positions=["OF"], recommendedBid=41, team="LAD", avg=0.289, hr=35, rbi=97, sb=17, ppaValue=93.8),
    DraftPlayerOut(id="3", name="Bobby Witt Jr.", positions=["SS"], recommendedBid=45, team="KC", avg=0.282, hr=31, rbi=97, sb=49, ppaValue=96.1),
    DraftPlayerOut(id="4", name="Aaron Judge", positions=["OF"], recommendedBid=44, team="NYY", avg=0.271, hr=50, rbi=118, sb=8, ppaValue=95.0),
    DraftPlayerOut(id="5", name="Freddie Freeman", positions=["1B"], recommendedBid=37, team="LAD", avg=0.308, hr=28, rbi=101, sb=16, ppaValue=90.7),
    DraftPlayerOut(id="6", name="Jose Ramirez", positions=["3B"], recommendedBid=36, team="CLE", avg=0.279, hr=31, rbi=102, sb=27, ppaValue=90.1),
    DraftPlayerOut(id="7", name="Francisco Lindor", positions=["SS"], recommendedBid=33, team="NYM", avg=0.271, hr=26, rbi=88, sb=29, ppaValue=86.4),
    DraftPlayerOut(id="8", name="Adley Rutschman", positions=["C"], recommendedBid=18, team="BAL", avg=0.268, hr=21, rbi=79, sb=2, ppaValue=72.2),
    DraftPlayerOut(id="9", name="Marcus Semien", positions=["2B"], recommendedBid=24, team="TEX", avg=0.274, hr=24, rbi=90, sb=14, ppaValue=79.5),
    DraftPlayerOut(id="10", name="Corey Seager", positions=["SS"], recommendedBid=31, team="TEX", avg=0.301, hr=33, rbi=97, sb=2, ppaValue=84.3),
    DraftPlayerOut(id="11", name="Juan Soto", positions=["OF"], recommendedBid=39, team="NYY", avg=0.288, hr=37, rbi=104, sb=9, ppaValue=91.7),
    DraftPlayerOut(id="12", name="Corbin Burnes", positions=["SP"], recommendedBid=28, team="BAL", avg=0.0, hr=0, rbi=0, sb=0, ppaValue=83.1),
    DraftPlayerOut(id="13", name="Zack Wheeler", positions=["SP"], recommendedBid=26, team="PHI", avg=0.0, hr=0, rbi=0, sb=0, ppaValue=81.9),
    DraftPlayerOut(id="14", name="Edwin Diaz", positions=["RP"], recommendedBid=16, team="NYM", avg=0.0, hr=0, rbi=0, sb=0, ppaValue=70.0),
    DraftPlayerOut(id="15", name="Josh Hader", positions=["RP"], recommendedBid=15, team="HOU", avg=0.0, hr=0, rbi=0, sb=0, ppaValue=68.9),
]

MOCK_DRAFT_POSITION_FILTERS: List[DraftPositionFilter] = [
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
]

MOCK_DRAFT_SORT_OPTIONS: List[DraftSortOption] = [
    DraftSortOption(value="score_desc", label="By Score (desc)"),
    DraftSortOption(value="score_asc", label="By Score (asc)"),
    DraftSortOption(value="cost_desc", label="By Draft Cost (desc)"),
    DraftSortOption(value="cost_asc", label="By Draft Cost (asc)"),
    DraftSortOption(value="avg_desc", label="By AVG"),
    DraftSortOption(value="hr_desc", label="By HR"),
    DraftSortOption(value="rbi_desc", label="By RBI"),
    DraftSortOption(value="sb_desc", label="By SB"),
]

DEFAULT_DRAFT_CONFIG = DraftConfigOut(
    leagueType="standard",
    budget=260,
    rosterPlayers=23,
    myTeamName="PPA-DUN",
    oppTeamName="Rivals",
    opponentsCount=5,
    oppTeamNames=["Rivals", "Blue Sox", "City Sluggers", "Night Owls", "Harbor Aces"],
)

DEFAULT_OPPONENT_POOL = ["Blue Sox", "City Sluggers", "Night Owls", "Harbor Aces", "River Sharks", "Iron Bats"]

# In-memory draft room state (replace with DB later).
DRAFT_PICKS_BY_ROOM: Dict[str, List[DraftPickOut]] = {"default": []}

SLOT_TEMPLATE_BASE: List[DraftPosition] = [
    "SP",
    "SP",
    "RP",
    "SP",
    "RP",
    "C",
    "1B",
    "2B",
    "3B",
    "SS",
    "OF",
    "OF",
    "OF",
    "UTIL",
    "UTIL",
    "BENCH",
    "BENCH",
    "BENCH",
    "BENCH",
    "BENCH",
    "BENCH",
    "BENCH",
    "BENCH",
    "BENCH",
    "BENCH",
]

# 들어온 숫자를 특정 범위 안으로 강제로 맞춰주는 함수
# 사용자가 이상한 값을 보내도, 자동으로 맞춰줌.
def clamp_int(value: Optional[int], min_value: int, max_value: int, fallback: int) -> int:
    if value is None:
        return fallback
    return max(min_value, min(max_value, int(value)))


# 드래프트 방에 들어갈 팀 목록을 생성하는 함수
# 
def build_draft_teams(my_team_name: str, opp_team_name: str, opponents_count: int) -> List[DraftTeamOut]:
    teams: List[DraftTeamOut] = [
        DraftTeamOut(id="team-me", name=my_team_name or "My Team", isMine=True)
    ]
    if opponents_count <= 0:
        return teams

    teams.append(DraftTeamOut(id="team-opp", name=opp_team_name or "Opponent", isMine=False))
    for i in range(max(0, opponents_count - 1)):
        fallback = DEFAULT_OPPONENT_POOL[i] if i < len(DEFAULT_OPPONENT_POOL) else f"Opponent {i + 2}"
        teams.append(DraftTeamOut(id=f"team-{i + 3}", name=fallback, isMine=False))
    return teams


def sort_draft_players(players: List[DraftPlayerOut], sort: DraftSort) -> List[DraftPlayerOut]:
    numeric = lambda value: value if value is not None else -1
    if sort == "score_desc":
        return sorted(players, key=lambda p: p.ppaValue, reverse=True)
    if sort == "score_asc":
        return sorted(players, key=lambda p: p.ppaValue)
    if sort == "cost_desc":
        return sorted(players, key=lambda p: p.recommendedBid, reverse=True)
    if sort == "cost_asc":
        return sorted(players, key=lambda p: p.recommendedBid)
    if sort == "avg_desc":
        return sorted(players, key=lambda p: numeric(p.avg), reverse=True)
    if sort == "hr_desc":
        return sorted(players, key=lambda p: numeric(p.hr), reverse=True)
    if sort == "rbi_desc":
        return sorted(players, key=lambda p: numeric(p.rbi), reverse=True)
    if sort == "sb_desc":
        return sorted(players, key=lambda p: numeric(p.sb), reverse=True)
    return players


def get_room_picks(room_id: str) -> List[DraftPickOut]:
    return DRAFT_PICKS_BY_ROOM.setdefault(room_id, [])


def find_draft_player(player_id: str) -> Optional[DraftPlayerOut]:
    for player in MOCK_DRAFT_PLAYERS:
        if player.id == player_id:
            return player
    return None


def clamp_roster_slots(roster_players: Optional[int]) -> int:
    fallback = DEFAULT_DRAFT_CONFIG.rosterPlayers
    if roster_players is None:
        return clamp_int(fallback, 8, len(SLOT_TEMPLATE_BASE), fallback)
    return clamp_int(roster_players, 8, len(SLOT_TEMPLATE_BASE), fallback)


def build_slot_template(roster_slots: int) -> List[DraftPosition]:
    return SLOT_TEMPLATE_BASE[:roster_slots]


def find_available_slot_index(
    team_id: str,
    desired_pos: DraftPosition,
    slot_template: List[DraftPosition],
    picks: List[DraftPickOut],
) -> int:
    occupied = {pick.slotIndex for pick in picks if pick.draftedByTeamId == team_id}

    for i, slot in enumerate(slot_template):
        if i in occupied:
            continue
        if slot == desired_pos:
            return i

    for i, slot in enumerate(slot_template):
        if i in occupied:
            continue
        if slot == "UTIL":
            return i

    for i, slot in enumerate(slot_template):
        if i in occupied:
            continue
        if slot == "BENCH":
            return i

    return -1


def normalized_config(
    league_type: str,
    budget: Optional[int],
    roster_players: Optional[int],
    my_team_name: str,
    opp_team_name: str,
    opponents_count: Optional[int],
) -> DraftConfigOut:
    normalized_budget = clamp_int(budget, 50, 600, DEFAULT_DRAFT_CONFIG.budget)
    normalized_roster = clamp_int(roster_players, 12, 35, DEFAULT_DRAFT_CONFIG.rosterPlayers)
    normalized_opponents = clamp_int(opponents_count, 0, 12, DEFAULT_DRAFT_CONFIG.opponentsCount)

    teams = build_draft_teams(
        my_team_name=my_team_name.strip() or DEFAULT_DRAFT_CONFIG.myTeamName,
        opp_team_name=opp_team_name.strip() or DEFAULT_DRAFT_CONFIG.oppTeamName,
        opponents_count=normalized_opponents,
    )
    opp_team_names = [t.name for t in teams if not t.isMine]
    return DraftConfigOut(
        leagueType=league_type or DEFAULT_DRAFT_CONFIG.leagueType,
        budget=normalized_budget,
        rosterPlayers=normalized_roster,
        myTeamName=teams[0].name,
        oppTeamName=opp_team_names[0] if opp_team_names else DEFAULT_DRAFT_CONFIG.oppTeamName,
        opponentsCount=normalized_opponents,
        oppTeamNames=opp_team_names,
    )


# Used by Draft page initial config if no stored setup exists.
@router.get("/config/default", response_model=DraftConfigOut)
def get_default_draft_config():
    return DEFAULT_DRAFT_CONFIG


# Used by Draft page position chips.
@router.get("/filters/positions", response_model=DraftPositionFiltersResponse)
def get_draft_position_filters():
    return DraftPositionFiltersResponse(positions=MOCK_DRAFT_POSITION_FILTERS)


# Used by Draft page sort dropdown.
@router.get("/filters/sorts", response_model=DraftSortFiltersResponse)
def get_draft_sort_filters():
    return DraftSortFiltersResponse(sorts=MOCK_DRAFT_SORT_OPTIONS)


# Used by Draft room board. Builds teams from user setup values.
@router.get("/teams", response_model=DraftTeamsResponse)
def get_draft_teams(
    my_team_name: str = Query(default=DEFAULT_DRAFT_CONFIG.myTeamName, alias="myTeamName"),
    opp_team_name: str = Query(default=DEFAULT_DRAFT_CONFIG.oppTeamName, alias="oppTeamName"),
    opponents_count: int = Query(default=DEFAULT_DRAFT_CONFIG.opponentsCount, alias="opponentsCount", ge=0, le=12),
):
    teams = build_draft_teams(my_team_name=my_team_name, opp_team_name=opp_team_name, opponents_count=opponents_count)
    return DraftTeamsResponse(items=teams)


# Used by Draft page player table. Server-side query/position/sort/paging.
@router.get("/players", response_model=DraftPlayerListResponse)
def get_draft_players(
    query: Optional[str] = Query(default=None),
    position: DraftPositionFilter = Query(default="ALL"),
    sort: DraftSort = Query(default="score_desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1),
):
    keyword = (query or "").strip().lower()
    normalized_position = position.upper()

    filtered = []
    for player in MOCK_DRAFT_PLAYERS:
        matches_keyword = (
            not keyword
            or keyword in player.name.lower()
            or keyword in player.team.lower()
            or any(keyword in pos.lower() for pos in player.positions)
        )
        matches_position = normalized_position == "ALL" or normalized_position in player.positions
        if matches_keyword and matches_position:
            filtered.append(player)

    sorted_players = sort_draft_players(filtered, sort)
    total = len(sorted_players)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    safe_page = min(page, total_pages) if total_pages > 0 else 1
    start = (safe_page - 1) * limit if total_pages > 0 else 0
    end = start + limit
    paged = sorted_players[start:end]

    return DraftPlayerListResponse(
        items=paged,
        page=safe_page,
        limit=limit,
        total=total,
        totalPages=total_pages,
    )


# Used by Draft page to restore draft board state.
@router.get("/picks", response_model=DraftPicksResponse)
def get_draft_picks(room_id: str = Query(default="default", alias="roomId")):
    return DraftPicksResponse(roomId=room_id, items=get_room_picks(room_id))


# Used by Add Bid modal. Returns allowed positions/default position for a team/player.
@router.get("/allowed-positions", response_model=DraftAllowedPositionsResponse)
def get_allowed_positions(
    player_id: str = Query(alias="playerId"),
    team_id: str = Query(alias="teamId"),
    room_id: str = Query(default="default", alias="roomId"),
    roster_players: Optional[int] = Query(default=None, alias="rosterPlayers"),
):
    player = find_draft_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    slot_template = build_slot_template(clamp_roster_slots(roster_players))
    picks = get_room_picks(room_id)
    allowed_positions = [
        pos
        for pos in player.positions
        if find_available_slot_index(team_id, pos, slot_template, picks) != -1
    ]

    return DraftAllowedPositionsResponse(
        roomId=room_id,
        teamId=team_id,
        playerId=player_id,
        allowedPositions=allowed_positions,
        defaultSelectedPos=allowed_positions[0] if allowed_positions else None,
    )


# Used by Draft Add/Taken actions. Upserts a player's draft pick state.
@router.post("/picks", response_model=DraftPicksResponse)
def upsert_draft_pick(
    payload: DraftPickUpsertIn,
    room_id: str = Query(default="default", alias="roomId"),
    roster_players: Optional[int] = Query(default=None, alias="rosterPlayers"),
):
    player = find_draft_player(payload.playerId)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    if payload.slotPos not in player.positions:
        raise HTTPException(status_code=400, detail="Invalid slot position for player")

    picks = get_room_picks(room_id)
    next_picks = [p for p in picks if p.playerId != payload.playerId]
    slot_template = build_slot_template(clamp_roster_slots(roster_players))
    resolved_slot_index = find_available_slot_index(
        payload.draftedByTeamId,
        payload.slotPos,
        slot_template,
        next_picks,
    )
    if resolved_slot_index == -1:
        raise HTTPException(status_code=409, detail="No available slot for selected position")

    next_picks.append(
        DraftPickOut(
            playerId=payload.playerId,
            draftedByTeamId=payload.draftedByTeamId,
            slotIndex=resolved_slot_index,
            slotPos=payload.slotPos,
            bid=payload.bid,
            type=payload.type,
        )
    )
    DRAFT_PICKS_BY_ROOM[room_id] = next_picks
    return DraftPicksResponse(roomId=room_id, items=next_picks)


# Used by Draft remove action. Removes pick by playerId.
@router.delete("/picks/{player_id}", response_model=DraftPicksResponse)
def delete_draft_pick(
    player_id: str,
    room_id: str = Query(default="default", alias="roomId"),
):
    picks = get_room_picks(room_id)
    next_picks = [p for p in picks if p.playerId != player_id]
    if len(next_picks) == len(picks):
        raise HTTPException(status_code=404, detail="Pick not found")
    DRAFT_PICKS_BY_ROOM[room_id] = next_picks
    return DraftPicksResponse(roomId=room_id, items=next_picks)


# Used when frontend wants one call for draft startup data.
@router.get("/bootstrap", response_model=DraftBootstrapResponse)
def get_draft_bootstrap(
    league_type: str = Query(default=DEFAULT_DRAFT_CONFIG.leagueType, alias="leagueType"),
    budget: Optional[int] = Query(default=None),
    roster_players: Optional[int] = Query(default=None, alias="rosterPlayers"),
    my_team_name: str = Query(default=DEFAULT_DRAFT_CONFIG.myTeamName, alias="myTeamName"),
    opp_team_name: str = Query(default=DEFAULT_DRAFT_CONFIG.oppTeamName, alias="oppTeamName"),
    opponents_count: Optional[int] = Query(default=None, alias="opponentsCount"),
    room_id: str = Query(default="default", alias="roomId"),
):
    config = normalized_config(
        league_type=league_type,
        budget=budget,
        roster_players=roster_players,
        my_team_name=my_team_name,
        opp_team_name=opp_team_name,
        opponents_count=opponents_count,
    )
    teams = build_draft_teams(config.myTeamName, config.oppTeamName, config.opponentsCount)
    picks = get_room_picks(room_id)
    return DraftBootstrapResponse(
        config=config,
        teams=teams,
        positionFilters=MOCK_DRAFT_POSITION_FILTERS,
        sortOptions=MOCK_DRAFT_SORT_OPTIONS,
        picks=picks,
    )
