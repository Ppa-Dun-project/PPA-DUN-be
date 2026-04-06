import logging
from typing import Dict, List, Literal, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from ppa_schemas import (
    BatterBidRequestIn,
    BatterStatsIn,
    DraftContextIn,
    LeagueContextIn,
    PitcherBidRequestIn,
    PitcherStatsIn,
)
from ppa_service import PpaAdapterService, PpaServiceError, get_ppa_adapter_service

from core.config import settings

# Used by Draft page APIs (config/filters/teams/players/picks).
router = APIRouter(prefix="/api/draft", tags=["draft"])
logger = logging.getLogger(__name__)

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
    oppTeamName="Opponent 1",
    opponentsCount=5,
    oppTeamNames=["Opponent 1", "Opponent 2", "Opponent 3", "Opponent 4", "Opponent 5"],
)


# In-memory draft room state (replace with DB later).
DRAFT_PICKS_BY_ROOM: Dict[str, List[DraftPickOut]] = {"default": []}
ROOM_STATE_VERSION: Dict[str, int] = {"default": 0}
ALLOWED_POSITIONS_CACHE: Dict[Tuple[str, int, str, str, int], List[DraftPosition]] = {}
OCCUPIED_SLOTS_CACHE: Dict[Tuple[str, int], Dict[str, Set[int]]] = {}
PLAYER_MARKET_CACHE: Dict[
    Tuple[str, int, int, int, int, int, int, Tuple[str, ...]],
    Tuple[int, float],
] = {}
PITCHER_POSITIONS: Set[str] = {"SP", "RP"}
BATTER_POSITIONS: Set[str] = {"C", "1B", "2B", "3B", "SS", "OF", "DH"}
DEFAULT_MY_TEAM_ID = "team-me"
MAX_EXTERNAL_BID_CALLS_PER_REQUEST = 40

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

    teams.append(DraftTeamOut(id="team-opp", name=opp_team_name or "Opponent 1", isMine=False))
    for i in range(max(0, opponents_count - 1)):
        fallback = f"Opponent {i + 2}"
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


def is_external_bid_enabled() -> bool:
    return bool(settings.EXTERNAL_API_BASE_URL and settings.EXTERNAL_API_KEY)


def is_pitcher(player: DraftPlayerOut) -> bool:
    return any(pos in PITCHER_POSITIONS for pos in player.positions)


def to_external_position(player: DraftPlayerOut, pitcher: bool) -> str:
    primary = player.positions[0] if player.positions else ("SP" if pitcher else "OF")
    normalized = primary.upper()
    if pitcher:
        return "RP" if normalized == "RP" else "SP"
    if normalized == "UTIL":
        return "DH"
    return normalized if normalized in BATTER_POSITIONS else "OF"


def build_batter_stats(player: DraftPlayerOut) -> BatterStatsIn:
    hr = max(0, int(player.hr or 0))
    rbi = max(0, int(player.rbi or 0))
    sb = max(0, int(player.sb or 0))
    avg = float(player.avg or 0.250)
    if avg <= 0:
        avg = 0.250
    runs = max(0, int(round((rbi * 0.55) + (hr * 0.8) + (sb * 0.3) + 30)))
    caught_stealing = min(sb, max(0, int(round(sb * 0.25))))
    return BatterStatsIn(
        AB=550,
        R=runs,
        HR=hr,
        RBI=rbi,
        SB=sb,
        CS=caught_stealing,
        AVG=avg,
    )


def build_pitcher_stats(player: DraftPlayerOut) -> PitcherStatsIn:
    # Keep payload generation independent from static ppaValue.
    baseline_bid = max(1, int(player.recommendedBid or 1))
    tier_scale = max(0.65, min(1.25, baseline_bid / 25.0))
    is_relief = "RP" in player.positions
    if is_relief:
        ip = round(60.0 * tier_scale, 1)
        wins = max(1, int(round(3 * tier_scale)))
        saves = max(5, int(round(30 * tier_scale)))
        strikeouts = max(35, int(round(80 * tier_scale)))
        era = max(1.8, round(3.4 - ((tier_scale - 1.0) * 0.9), 2))
        whip = max(0.85, round(1.12 - ((tier_scale - 1.0) * 0.16), 2))
    else:
        ip = round(170.0 * tier_scale, 1)
        wins = max(3, int(round(11 * tier_scale)))
        saves = 0
        strikeouts = max(80, int(round(185 * tier_scale)))
        era = max(2.2, round(3.8 - ((tier_scale - 1.0) * 0.9), 2))
        whip = max(0.92, round(1.2 - ((tier_scale - 1.0) * 0.14), 2))
    return PitcherStatsIn(
        IP=ip,
        W=wins,
        SV=saves,
        K=strikeouts,
        ERA=era,
        WHIP=whip,
    )


def build_league_context(
    budget: int,
    roster_slots: int,
    opponents_count: int,
) -> LeagueContextIn:
    league_size = max(1, opponents_count + 1)
    return LeagueContextIn(
        leagueSize=league_size,
        rosterSize=max(1, roster_slots),
        totalBudget=max(1, budget * league_size),
    )


def build_draft_context(
    room_id: str,
    my_team_id: str,
    budget: int,
    roster_slots: int,
) -> DraftContextIn:
    picks = get_room_picks(room_id)
    my_picks = [pick for pick in picks if pick.draftedByTeamId == my_team_id]
    spent_budget = sum(pick.bid for pick in my_picks if isinstance(pick.bid, int))
    return DraftContextIn(
        myRemainingBudget=max(0, budget - spent_budget),
        myRemainingRosterSpots=max(1, roster_slots - len(my_picks)),
        myPositionsFilled=[pick.slotPos for pick in my_picks],
        draftedPlayersCount=len(picks),
    )


def resolve_player_market_values(
    player: DraftPlayerOut,
    league_context: LeagueContextIn,
    draft_context: DraftContextIn,
    service: PpaAdapterService,
) -> Tuple[int, float]:
    cache_key = (
        player.id,
        league_context.leagueSize,
        league_context.rosterSize,
        league_context.totalBudget,
        draft_context.myRemainingBudget,
        draft_context.myRemainingRosterSpots,
        draft_context.draftedPlayersCount,
        tuple(draft_context.myPositionsFilled),
    )
    cached = PLAYER_MARKET_CACHE.get(cache_key)
    if cached is not None:
        return cached

    pitcher = is_pitcher(player)
    position = to_external_position(player, pitcher=pitcher)
    try:
        if pitcher:
            payload = PitcherBidRequestIn(
                playerName=player.name,
                playerType="pitcher",
                position=position,
                stats=build_pitcher_stats(player),
                leagueContext=league_context,
                draftContext=draft_context,
            )
        else:
            payload = BatterBidRequestIn(
                playerName=player.name,
                playerType="batter",
                position=position,
                stats=build_batter_stats(player),
                leagueContext=league_context,
                draftContext=draft_context,
            )

        response = service.calculate_player_bid(payload)
        resolved_bid = max(1, int(getattr(response, "recommendedBid", player.recommendedBid)))
        resolved_value = float(getattr(response, "playerValue", player.ppaValue))
        resolved_pair = (resolved_bid, resolved_value)
        PLAYER_MARKET_CACHE[cache_key] = resolved_pair
        return resolved_pair
    except PpaServiceError as exc:
        logger.debug("Bid recommendation fallback for player=%s: %s", player.id, exc.detail)
        return (player.recommendedBid, player.ppaValue)
    except Exception:
        logger.exception("Unexpected bid recommendation fallback for player=%s", player.id)
        return (player.recommendedBid, player.ppaValue)


def enrich_players_with_external_bid(
    players: List[DraftPlayerOut],
    league_context: LeagueContextIn,
    draft_context: DraftContextIn,
    service: PpaAdapterService,
) -> List[DraftPlayerOut]:
    enriched: List[DraftPlayerOut] = []
    for player in players:
        resolved_bid, resolved_value = resolve_player_market_values(
            player=player,
            league_context=league_context,
            draft_context=draft_context,
            service=service,
        )
        enriched.append(
            player.model_copy(
                update={
                    "recommendedBid": resolved_bid,
                    "ppaValue": resolved_value,
                }
            )
        )
    return enriched


def get_room_version(room_id: str) -> int:
    return ROOM_STATE_VERSION.setdefault(room_id, 0)


def clear_room_caches(room_id: str) -> None:
    allowed_keys = [key for key in ALLOWED_POSITIONS_CACHE if key[0] == room_id]
    for key in allowed_keys:
        ALLOWED_POSITIONS_CACHE.pop(key, None)

    occupied_keys = [key for key in OCCUPIED_SLOTS_CACHE if key[0] == room_id]
    for key in occupied_keys:
        OCCUPIED_SLOTS_CACHE.pop(key, None)


def bump_room_version(room_id: str) -> None:
    ROOM_STATE_VERSION[room_id] = get_room_version(room_id) + 1
    clear_room_caches(room_id)


def get_room_picks(room_id: str) -> List[DraftPickOut]:
    get_room_version(room_id)
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


def find_available_slot_index_with_occupied(
    desired_pos: DraftPosition,
    slot_template: List[DraftPosition],
    occupied: Set[int],
) -> int:
    # Position rule removed: assign the first open slot regardless of player position.
    for i, _slot in enumerate(slot_template):
        if i in occupied:
            continue
        return i
    return -1


def find_available_slot_index(
    team_id: str,
    desired_pos: DraftPosition,
    slot_template: List[DraftPosition],
    picks: List[DraftPickOut],
) -> int:
    occupied = {pick.slotIndex for pick in picks if pick.draftedByTeamId == team_id}
    return find_available_slot_index_with_occupied(desired_pos, slot_template, occupied)


def get_occupied_slots_by_team(
    room_id: str,
    room_version: int,
    picks: List[DraftPickOut],
) -> Dict[str, Set[int]]:
    cache_key = (room_id, room_version)
    cached = OCCUPIED_SLOTS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    occupied_by_team: Dict[str, Set[int]] = {}
    for pick in picks:
        occupied_by_team.setdefault(pick.draftedByTeamId, set()).add(pick.slotIndex)

    OCCUPIED_SLOTS_CACHE[cache_key] = occupied_by_team
    return occupied_by_team


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
    room_id: str = Query(default="default", alias="roomId"),
    my_team_id: str = Query(default=DEFAULT_MY_TEAM_ID, alias="myTeamId"),
    budget: int = Query(default=DEFAULT_DRAFT_CONFIG.budget, ge=50, le=600),
    roster_players: int = Query(default=DEFAULT_DRAFT_CONFIG.rosterPlayers, alias="rosterPlayers", ge=8, le=len(SLOT_TEMPLATE_BASE)),
    opponents_count: int = Query(default=DEFAULT_DRAFT_CONFIG.opponentsCount, alias="opponentsCount", ge=0, le=12),
    service: PpaAdapterService = Depends(get_ppa_adapter_service),
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

    roster_slots = clamp_roster_slots(roster_players)
    if is_external_bid_enabled() and paged:
        league_context = build_league_context(
            budget=budget,
            roster_slots=roster_slots,
            opponents_count=opponents_count,
        )
        draft_context = build_draft_context(
            room_id=room_id,
            my_team_id=my_team_id,
            budget=budget,
            roster_slots=roster_slots,
        )
        external_target = paged[:MAX_EXTERNAL_BID_CALLS_PER_REQUEST]
        enriched = enrich_players_with_external_bid(
            players=external_target,
            league_context=league_context,
            draft_context=draft_context,
            service=service,
        )
        paged = enriched + paged[len(external_target):]

        if sort in ("cost_desc", "cost_asc", "score_desc", "score_asc"):
            paged = sort_draft_players(paged, sort)

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

    roster_slots = clamp_roster_slots(roster_players)
    room_version = get_room_version(room_id)
    cache_key = (room_id, room_version, team_id, player_id, roster_slots)
    cached = ALLOWED_POSITIONS_CACHE.get(cache_key)
    if cached is not None:
        return DraftAllowedPositionsResponse(
            roomId=room_id,
            teamId=team_id,
            playerId=player_id,
            allowedPositions=cached,
            defaultSelectedPos=cached[0] if cached else None,
        )

    slot_template = build_slot_template(roster_slots)
    picks = get_room_picks(room_id)
    occupied_by_team = get_occupied_slots_by_team(room_id, room_version, picks)
    team_occupied = occupied_by_team.get(team_id, set())
    first_position = player.positions[0] if player.positions else "UTIL"
    has_open_slot = (
        find_available_slot_index_with_occupied(first_position, slot_template, team_occupied)
        != -1
    )
    allowed_positions = list(player.positions) if has_open_slot else []
    ALLOWED_POSITIONS_CACHE[cache_key] = allowed_positions

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

    picks = get_room_picks(room_id)
    next_picks = [p for p in picks if p.playerId != payload.playerId]
    slot_template = build_slot_template(clamp_roster_slots(roster_players))
    occupied = {
        pick.slotIndex
        for pick in next_picks
        if pick.draftedByTeamId == payload.draftedByTeamId
    }
    resolved_slot_index = find_available_slot_index_with_occupied(
        payload.slotPos,
        slot_template,
        occupied,
    )
    if resolved_slot_index == -1:
        raise HTTPException(status_code=409, detail="No available slot for team roster")

    resolved_slot_pos = slot_template[resolved_slot_index]

    next_picks.append(
        DraftPickOut(
            playerId=payload.playerId,
            draftedByTeamId=payload.draftedByTeamId,
            slotIndex=resolved_slot_index,
            slotPos=resolved_slot_pos,
            bid=payload.bid,
            type=payload.type,
        )
    )
    DRAFT_PICKS_BY_ROOM[room_id] = next_picks
    bump_room_version(room_id)
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
    bump_room_version(room_id)
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
