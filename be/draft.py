# Draft page API router.
# Handles draft configuration, player listing with DB-backed PPA scores,
# pick registration/deletion (persisted to DB), slot assignment, and bootstrap.
# When a user opens the Draft page, /bootstrap loads all necessary data in one call.
# Player value scores and recommended bids come from the player_ppa_scores table.
import logging
from typing import Dict, List, Literal, Optional, Set, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text as sa_text


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


# DB position -> draft position mapping
_DB_POS_TO_DRAFT: Dict[str, DraftPosition] = {
    "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
    "OF": "OF", "LF": "OF", "CF": "OF", "RF": "OF",
    "DH": "UTIL", "TWP": "UTIL", "IF": "SS",
    "P": "SP",
}

# Builds SQL WHERE clause for draft position filtering
def _draft_position_filter_sql(position: str) -> str:
    if position == "ALL":
        return ""
    if position == "SP":
        return "AND p.position = 'P'"
    if position == "RP":
        return "AND p.position = 'P'"
    if position == "OF":
        return "AND p.position IN ('OF','LF','CF','RF')"
    if position == "UTIL":
        return ""  # UTIL allows all players
    return f"AND p.position = :position"

# Builds SQL ORDER BY clause for draft player sorting
def _draft_sort_sql(sort: str) -> str:
    if sort == "score_desc":
        return "ORDER BY COALESCE(ppa.value_score, 0) DESC, p.full_name ASC"
    if sort == "score_asc":
        return "ORDER BY COALESCE(ppa.value_score, 0) ASC, p.full_name ASC"
    if sort == "cost_desc":
        return "ORDER BY COALESCE(ppa.value_score, 0) DESC, p.full_name ASC"
    if sort == "cost_asc":
        return "ORDER BY COALESCE(ppa.value_score, 0) ASC, p.full_name ASC"
    if sort == "avg_desc":
        return "ORDER BY COALESCE(s.AVG, 0) DESC, p.full_name ASC"
    if sort == "hr_desc":
        return "ORDER BY COALESCE(s.HR, 0) DESC, p.full_name ASC"
    if sort == "rbi_desc":
        return "ORDER BY COALESCE(s.RBI, 0) DESC, p.full_name ASC"
    if sort == "sb_desc":
        return "ORDER BY COALESCE(s.SB, 0) DESC, p.full_name ASC"
    return "ORDER BY COALESCE(ppa.value_score, 0) DESC, p.full_name ASC"


_DRAFT_BASE_QUERY = """
    FROM mlb_players_list p
    LEFT JOIN mlb_team_list t ON p.team_id = t.team_id
    LEFT JOIN players_stats_nl_2025 s ON LOWER(s.Player) LIKE CONCAT(LOWER(p.full_name), ' %')
    LEFT JOIN player_ppa_scores ppa ON p.player_id = ppa.player_id
    WHERE p.active = 1
"""


def _row_to_draft_player(row) -> DraftPlayerOut:
    """Converts a DB row into a DraftPlayerOut model."""
    r = row._mapping
    raw_pos = r["position"] or "DH"
    draft_pos = _DB_POS_TO_DRAFT.get(raw_pos, "UTIL")
    ppa_value = float(r.get("value_score") or 0)
    recommended_bid = int(r.get("recommended_bid") or 0)

    return DraftPlayerOut(
        id=str(r["player_id"]),
        name=r["full_name"],
        positions=[draft_pos],
        recommendedBid=max(1, recommended_bid) if recommended_bid > 0 else 1,
        team=r["abbreviation"] or "",
        avg=round(float(r.get("AVG") or 0), 3) or None,
        hr=int(r.get("HR") or 0) or None,
        rbi=int(r.get("RBI") or 0) or None,
        sb=int(r.get("SB") or 0) or None,
        ppaValue=round(ppa_value, 1),
    )

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


# DB-backed draft storage
from database.draft_store import (
    ensure_draft_tables,
    save_draft_config,
    load_draft_config,
    load_draft_picks,
    upsert_draft_pick,
    delete_draft_pick,
    reset_draft,
    save_all_picks,
)
ensure_draft_tables()

# In-memory caches for performance (cleared when picks change)
ALLOWED_POSITIONS_CACHE: Dict[Tuple[str, str, str, int], List[DraftPosition]] = {}
OCCUPIED_SLOTS_CACHE: Dict[str, Dict[str, Set[int]]] = {}
DEFAULT_MY_TEAM_ID = "team-0"

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

# Clamps a number to a given range. Ensures user input stays within valid bounds.
def clamp_int(value: Optional[int], min_value: int, max_value: int, fallback: int) -> int:
    if value is None:
        return fallback
    return max(min_value, min(max_value, int(value)))


# Builds the list of teams for a draft room.
# opp_team_names: user-provided opponent names (auto-generated if empty)
def build_draft_teams(my_team_name: str, opp_team_names: List[str], opponents_count: int) -> List[DraftTeamOut]:
    teams: List[DraftTeamOut] = [
        DraftTeamOut(id="team-0", name=my_team_name or "My Team", isMine=True)
    ]
    for i in range(max(0, opponents_count)):
        name = opp_team_names[i] if i < len(opp_team_names) and opp_team_names[i] else f"Opponent {i + 1}"
        teams.append(DraftTeamOut(id=f"team-{i + 1}", name=name, isMine=False))
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




def clear_user_caches(user_id: str) -> None:
    """Clears cached positions/slots for a user when picks change."""
    allowed_keys = [key for key in ALLOWED_POSITIONS_CACHE if key[0] == user_id]
    for key in allowed_keys:
        ALLOWED_POSITIONS_CACHE.pop(key, None)
    OCCUPIED_SLOTS_CACHE.pop(user_id, None)


def get_user_picks(user_id: str) -> List[DraftPickOut]:
    """Loads all draft picks for a user from the database."""
    rows = load_draft_picks(user_id)
    return [
        DraftPickOut(
            playerId=r["playerId"],
            draftedByTeamId=r["draftedByTeamId"],
            slotIndex=r["slotIndex"],
            slotPos=r["slotPos"],
            bid=r["bid"],
            type=r["type"],
        )
        for r in rows
    ]


def find_draft_player(player_id: str) -> Optional[DraftPlayerOut]:
    """Looks up a single player by player_id from the database."""
    from database.draft_store import engine
    sql = sa_text(f"""
        SELECT p.player_id, p.full_name, p.position, t.abbreviation,
               s.AVG, s.HR, s.RBI, s.SB, ppa.value_score, ppa.recommended_bid
        {_DRAFT_BASE_QUERY} AND p.player_id = :player_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"player_id": int(player_id)}).fetchone()
    if not row:
        return None
    return _row_to_draft_player(row)


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
    user_id: str,
    picks: List[DraftPickOut],
) -> Dict[str, Set[int]]:
    cached = OCCUPIED_SLOTS_CACHE.get(user_id)
    if cached is not None:
        return cached

    occupied_by_team: Dict[str, Set[int]] = {}
    for pick in picks:
        occupied_by_team.setdefault(pick.draftedByTeamId, set()).add(pick.slotIndex)

    OCCUPIED_SLOTS_CACHE[user_id] = occupied_by_team
    return occupied_by_team


def normalized_config(
    league_type: str,
    budget: Optional[int],
    roster_players: Optional[int],
    my_team_name: str,
    opp_team_names: List[str],
    opponents_count: Optional[int],
) -> Tuple[DraftConfigOut, List[DraftTeamOut]]:
    
    # Normalize user-provided values into valid ranges.
    normalized_budget = clamp_int(budget, 50, 600, DEFAULT_DRAFT_CONFIG.budget)
    normalized_roster = clamp_int(roster_players, 12, 35, DEFAULT_DRAFT_CONFIG.rosterPlayers)
    normalized_opponents = clamp_int(opponents_count, 0, 12, DEFAULT_DRAFT_CONFIG.opponentsCount)

    teams = build_draft_teams(
        my_team_name=my_team_name.strip() or DEFAULT_DRAFT_CONFIG.myTeamName,
        opp_team_names=opp_team_names,
        opponents_count=normalized_opponents,
    )
    resolved_opp_names = [t.name for t in teams if not t.isMine]
    
    config = DraftConfigOut(
        leagueType=league_type or DEFAULT_DRAFT_CONFIG.leagueType,
        budget=normalized_budget,
        rosterPlayers=normalized_roster,
        myTeamName=teams[0].name,
        oppTeamName=resolved_opp_names[0] if resolved_opp_names else DEFAULT_DRAFT_CONFIG.oppTeamName,
        opponentsCount=normalized_opponents,
        oppTeamNames=resolved_opp_names,
    )
    return config, teams


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
    opp_team_names_raw: str = Query(default="", alias="oppTeamNames"),
    opponents_count: int = Query(default=DEFAULT_DRAFT_CONFIG.opponentsCount, alias="opponentsCount", ge=0, le=12),
):
    opp_team_names = [n.strip() for n in opp_team_names_raw.split(",") if n.strip()] if opp_team_names_raw else []
    teams = build_draft_teams(my_team_name=my_team_name, opp_team_names=opp_team_names, opponents_count=opponents_count)
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
    from database.draft_store import engine

    keyword = (query or "").strip().lower()
    normalized_position = position.upper()

    # Build WHERE clause
    where_parts = []
    params: Dict = {}

    if keyword:
        where_parts.append(
            "(LOWER(p.full_name) LIKE :keyword OR LOWER(t.abbreviation) LIKE :keyword)"
        )
        params["keyword"] = f"%{keyword}%"

    pos_sql = _draft_position_filter_sql(normalized_position)
    if pos_sql and ":position" in pos_sql:
        params["position"] = normalized_position

    extra_where = (" AND " + " AND ".join(where_parts)) if where_parts else ""
    sort_sql = _draft_sort_sql(sort)

    # COUNT
    count_sql = sa_text(f"SELECT COUNT(*) {_DRAFT_BASE_QUERY} {extra_where} {pos_sql}")
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar()

    total_pages = (total + limit - 1) // limit if total > 0 else 0
    safe_page = min(page, total_pages) if total_pages > 0 else 1
    offset = (safe_page - 1) * limit if total_pages > 0 else 0

    # DATA
    data_sql = sa_text(f"""
        SELECT p.player_id, p.full_name, p.position, t.abbreviation,
               s.AVG, s.HR, s.RBI, s.SB, ppa.value_score, ppa.recommended_bid
        {_DRAFT_BASE_QUERY} {extra_where} {pos_sql}
        {sort_sql}
        LIMIT :limit OFFSET :offset
    """)
    params["limit"] = limit
    params["offset"] = offset

    with engine.connect() as conn:
        rows = conn.execute(data_sql, params).fetchall()

    paged = [_row_to_draft_player(r) for r in rows]

    return DraftPlayerListResponse(
        items=paged,
        page=safe_page,
        limit=limit,
        total=total,
        totalPages=total_pages,
    )


# Used by Draft page to restore draft board state.
@router.get("/picks", response_model=DraftPicksResponse)
def get_draft_picks(user_id: str = Query(default="default", alias="userId")):
    return DraftPicksResponse(roomId=user_id, items=get_user_picks(user_id))


# Used by Add Bid modal. Returns allowed positions/default position for a team/player.
@router.get("/allowed-positions", response_model=DraftAllowedPositionsResponse)
def get_allowed_positions(
    player_id: str = Query(alias="playerId"),
    team_id: str = Query(alias="teamId"),
    user_id: str = Query(default="default", alias="userId"),
    roster_players: Optional[int] = Query(default=None, alias="rosterPlayers"),
):
    player = find_draft_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    roster_slots = clamp_roster_slots(roster_players)
    cache_key = (user_id, team_id, player_id, roster_slots)
    cached = ALLOWED_POSITIONS_CACHE.get(cache_key)
    if cached is not None:
        return DraftAllowedPositionsResponse(
            roomId=user_id,
            teamId=team_id,
            playerId=player_id,
            allowedPositions=cached,
            defaultSelectedPos=cached[0] if cached else None,
        )

    slot_template = build_slot_template(roster_slots)
    picks = get_user_picks(user_id)
    occupied_by_team = get_occupied_slots_by_team(user_id, picks)
    team_occupied = occupied_by_team.get(team_id, set())
    first_position = player.positions[0] if player.positions else "UTIL"
    has_open_slot = (
        find_available_slot_index_with_occupied(first_position, slot_template, team_occupied)
        != -1
    )
    allowed_positions = list(player.positions) if has_open_slot else []
    ALLOWED_POSITIONS_CACHE[cache_key] = allowed_positions

    return DraftAllowedPositionsResponse(
        roomId=user_id,
        teamId=team_id,
        playerId=player_id,
        allowedPositions=allowed_positions,
        defaultSelectedPos=allowed_positions[0] if allowed_positions else None,
    )


# Used by Draft Add/Taken actions. Upserts a player's draft pick state.
@router.post("/picks", response_model=DraftPicksResponse)
def upsert_draft_pick_endpoint(
    payload: DraftPickUpsertIn,
    user_id: str = Query(default="default", alias="userId"),
    roster_players: Optional[int] = Query(default=None, alias="rosterPlayers"),
):
    player = find_draft_player(payload.playerId)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    picks = get_user_picks(user_id)
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

    # Persist pick to DB
    upsert_draft_pick(
        user_id=user_id,
        player_id=payload.playerId,
        drafted_by_team_id=payload.draftedByTeamId,
        slot_index=resolved_slot_index,
        slot_pos=resolved_slot_pos,
        bid=payload.bid,
        pick_type=payload.type,
    )
    clear_user_caches(user_id)

    all_picks = get_user_picks(user_id)
    return DraftPicksResponse(roomId=user_id, items=all_picks)


# Used by Draft remove action. Removes pick by playerId.
@router.delete("/picks/{player_id}", response_model=DraftPicksResponse)
def delete_draft_pick_endpoint(
    player_id: str,
    user_id: str = Query(default="default", alias="userId"),
):
    deleted = delete_draft_pick(user_id, player_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Pick not found")
    clear_user_caches(user_id)

    all_picks = get_user_picks(user_id)
    return DraftPicksResponse(roomId=user_id, items=all_picks)


# Automatically called by Draft page on load to get all necessary data in one request (config/teams/filters/picks).
# Returns all data needed by the Draft page in a single response on page load.
@router.get("/bootstrap", response_model=DraftBootstrapResponse)
def get_draft_bootstrap(
    league_type: str = Query(default=DEFAULT_DRAFT_CONFIG.leagueType, alias="leagueType"),
    budget: Optional[int] = Query(default=None),
    roster_players: Optional[int] = Query(default=None, alias="rosterPlayers"),
    my_team_name: str = Query(default=DEFAULT_DRAFT_CONFIG.myTeamName, alias="myTeamName"),
    opp_team_names_raw: str = Query(default="", alias="oppTeamNames"),
    opponents_count: Optional[int] = Query(default=None, alias="opponentsCount"),
    user_id: str = Query(default="default", alias="userId"),
):
    opp_team_names = [n.strip() for n in opp_team_names_raw.split(",") if n.strip()] if opp_team_names_raw else []
    config, teams = normalized_config(
        league_type=league_type,
        budget=budget,
        roster_players=roster_players,
        my_team_name=my_team_name,
        opp_team_names=opp_team_names,
        opponents_count=opponents_count,
    )

    # Save config to DB
    save_draft_config(
        user_id=user_id,
        league_type=config.leagueType,
        budget=config.budget,
        roster_players=config.rosterPlayers,
        my_team_name=config.myTeamName,
        opp_team_names=config.oppTeamNames,
        opponents_count=config.opponentsCount,
    )

    picks = get_user_picks(user_id)
    return DraftBootstrapResponse(
        config=config,
        teams=teams,
        positionFilters=MOCK_DRAFT_POSITION_FILTERS,
        sortOptions=MOCK_DRAFT_SORT_OPTIONS,
        picks=picks,
    )


# Resets user's entire draft (config + all picks deleted).
@router.delete("/reset", response_model=dict)
def reset_draft_endpoint(
    user_id: str = Query(default="default", alias="userId"),
):
    reset_draft(user_id)
    clear_user_caches(user_id)
    return {"status": "ok", "userId": user_id}
