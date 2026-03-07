from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Used by Player pages. This router owns player list/detail/filter APIs.
router = APIRouter(prefix="/api/players", tags=["players"])


# Used by PlayerDetail page. 선수의 상세 스탯 블록.
class PlayerStats(BaseModel):
    # 경기 수, 타석 수, 홈런 수, OPS (타자)
    g: int
    pa: int
    hr: int
    ops: float
    
    # 이닝 수 (투수)
    ip: float = 0.0

# Used by PlayerDetail page. 선수 한명의 풀 데이터
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
    # 선수 사진 URL (선택적)
    headshotUrl: Optional[str] = None
    stats: PlayerStats

# Used by player list/table cards. 테이블에 적을 주요 정보.
class PlayerListItem(BaseModel):
    id: int
    name: str
    team: str
    positions: List[str]
    valueScore: float
    headshotUrl: Optional[str] = None

# Player list with 페이지네이션. (응답 형식)
class PlayerListResponse(BaseModel):
    items: List[PlayerListItem]
    page: int
    limit: int
    total: int
    totalPages: int


# Used by PlayersToolbar position chips. 포지션 필터링 목록 응답 형식
class PlayerPositionFiltersResponse(BaseModel):
    positions: List[str]

# Used by PlayersToolbar sort dropdown. 
# value_desc = ValueScore 내림차순, name_asc = 이름 오름차순 등
class PlayerSortOption(BaseModel):
    value: str
    label: str

# Used by PlayersToolbar sort dropdown. 
# 위에서 매칭된 정렬 옵션 목록 응답 형식
class PlayerSortFiltersResponse(BaseModel):
    sorts: List[PlayerSortOption]

SortOrder = Literal["value_desc", "value_asc", "name_asc", "name_desc"]

# Mock source for player list/detail (later replace with DB rows).
MOCK_PLAYERS: List[PlayerOut] = [
    PlayerOut(
        id=1,
        name="Aaron Judge",
        age=33,
        height_in=79,
        weight_lb=282,
        bats="R",
        throws="R",
        team="NYY",
        positions=["OF"],
        valueScore=98.2,
        stats=PlayerStats(g=145, pa=650, hr=37, ops=0.980, ip=0.0),
    ),
    PlayerOut(
        id=2,
        name="Mookie Betts",
        age=32,
        height_in=70,
        weight_lb=180,
        bats="R",
        throws="R",
        team="LAD",
        positions=["2B", "OF"],
        valueScore=95.4,
        stats=PlayerStats(g=148, pa=693, hr=39, ops=0.987, ip=0.0),
    ),
    PlayerOut(
        id=3,
        name="Shohei Ohtani",
        age=30,
        height_in=76,
        weight_lb=210,
        bats="L",
        throws="R",
        team="LAD",
        positions=["DH", "SP"],
        valueScore=99.5,
        stats=PlayerStats(g=152, pa=701, hr=44, ops=1.021, ip=0.0),
    ),
    PlayerOut(
        id=4,
        name="Ronald Acuna Jr.",
        age=27,
        height_in=72,
        weight_lb=205,
        bats="R",
        throws="R",
        team="ATL",
        positions=["OF"],
        valueScore=96.8,
        stats=PlayerStats(g=149, pa=710, hr=35, ops=0.944, ip=0.0),
    ),
    PlayerOut(
        id=5,
        name="Freddie Freeman",
        age=35,
        height_in=77,
        weight_lb=220,
        bats="L",
        throws="R",
        team="LAD",
        positions=["1B"],
        valueScore=94.6,
        stats=PlayerStats(g=156, pa=721, hr=29, ops=0.931, ip=0.0),
    ),
    PlayerOut(
        id=6,
        name="Juan Soto",
        age=26,
        height_in=74,
        weight_lb=224,
        bats="L",
        throws="L",
        team="NYY",
        positions=["OF"],
        valueScore=97.1,
        stats=PlayerStats(g=151, pa=702, hr=34, ops=0.978, ip=0.0),
    ),
    PlayerOut(
        id=7,
        name="Bobby Witt Jr.",
        age=25,
        height_in=73,
        weight_lb=200,
        bats="R",
        throws="R",
        team="KC",
        positions=["SS"],
        valueScore=93.9,
        stats=PlayerStats(g=158, pa=725, hr=31, ops=0.911, ip=0.0),
    ),
    PlayerOut(
        id=8,
        name="Corey Seager",
        age=31,
        height_in=76,
        weight_lb=215,
        bats="L",
        throws="R",
        team="TEX",
        positions=["SS"],
        valueScore=91.7,
        stats=PlayerStats(g=138, pa=602, hr=33, ops=0.946, ip=0.0),
    ),
    PlayerOut(
        id=9,
        name="Jose Ramirez",
        age=32,
        height_in=69,
        weight_lb=190,
        bats="S",
        throws="R",
        team="CLE",
        positions=["3B"],
        valueScore=90.8,
        stats=PlayerStats(g=154, pa=677, hr=28, ops=0.872, ip=0.0),
    ),
    PlayerOut(
        id=10,
        name="Adley Rutschman",
        age=27,
        height_in=74,
        weight_lb=230,
        bats="S",
        throws="R",
        team="BAL",
        positions=["C"],
        valueScore=85.6,
        stats=PlayerStats(g=143, pa=635, hr=24, ops=0.821, ip=0.0),
    ),
    PlayerOut(
        id=11,
        name="Gerrit Cole",
        age=34,
        height_in=76,
        weight_lb=220,
        bats="R",
        throws="R",
        team="NYY",
        positions=["SP"],
        valueScore=92.4,
        stats=PlayerStats(g=32, pa=0, hr=0, ops=0.000, ip=198.2),
    ),
    PlayerOut(
        id=12,
        name="Zack Wheeler",
        age=35,
        height_in=76,
        weight_lb=195,
        bats="L",
        throws="R",
        team="PHI",
        positions=["SP"],
        valueScore=89.1,
        stats=PlayerStats(g=33, pa=0, hr=0, ops=0.000, ip=205.1),
    ),
    PlayerOut(
        id=13,
        name="Corbin Burnes",
        age=30,
        height_in=75,
        weight_lb=245,
        bats="R",
        throws="R",
        team="BAL",
        positions=["SP"],
        valueScore=88.3,
        stats=PlayerStats(g=31, pa=0, hr=0, ops=0.000, ip=193.0),
    ),
    PlayerOut(
        id=14,
        name="Emmanuel Clase",
        age=27,
        height_in=74,
        weight_lb=215,
        bats="R",
        throws="R",
        team="CLE",
        positions=["RP"],
        valueScore=83.5,
        stats=PlayerStats(g=71, pa=0, hr=0, ops=0.000, ip=72.1),
    ),
    PlayerOut(
        id=15,
        name="Josh Hader",
        age=31,
        height_in=75,
        weight_lb=195,
        bats="L",
        throws="L",
        team="HOU",
        positions=["RP"],
        valueScore=81.9,
        stats=PlayerStats(g=66, pa=0, hr=0, ops=0.000, ip=64.2),
    ),
]

# Used by PlayersToolbar position chips.
MOCK_PLAYER_POSITION_FILTERS: List[str] = ["ALL", "C", "1B", "2B", "3B", "SS", "OF", "P", "DH"]

# Used by PlayersToolbar sort dropdown.
# 드롭다운 옵션 추가하고 싶으면 여기에 하면 됨
MOCK_PLAYER_SORT_OPTIONS: List[PlayerSortOption] = [
    PlayerSortOption(value="value_desc", label="ValueScore (high -> low)"),
    PlayerSortOption(value="value_asc", label="ValueScore (low -> high)"),
    PlayerSortOption(value="name_asc", label="Name (A -> Z)"),
    PlayerSortOption(value="name_desc", label="Name (Z -> A)"),
]


def sort_players(players: List[PlayerOut], sort: SortOrder) -> List[PlayerOut]:
    if sort == "value_desc":
        return sorted(players, key=lambda p: p.valueScore, reverse=True)
    if sort == "value_asc":
        return sorted(players, key=lambda p: p.valueScore)
    if sort == "name_asc":
        return sorted(players, key=lambda p: p.name.lower())
    if sort == "name_desc":
        return sorted(players, key=lambda p: p.name.lower(), reverse=True)
    return players

# 선수 포지션이 현재 필터 조건과 맞는지 검사
def matches_position_filter(player_positions: List[str], normalized_position: str) -> bool:
    # 대문자로 통일
    normalized = {pos.upper() for pos in player_positions}
    if normalized_position == "ALL":
        return True
    
    # Supports UI filter "P" while preserving SP/RP data in records.
    if normalized_position == "P":
        return bool(normalized.intersection({"P", "SP", "RP"}))
    return normalized_position in normalized


# Used by PlayersToolbar. Returns all available player positions.
# 위에서 정한, 포지션 칩 옵션 제공 api.
# 만약에 포지션을 더 추가하고 싶으면 여기 추가 하면 됨.
@router.get("/filters/positions", response_model=PlayerPositionFiltersResponse)
def get_player_position_filters():
    return PlayerPositionFiltersResponse(positions=MOCK_PLAYER_POSITION_FILTERS)


# Used by PlayersToolbar. Returns all available sort options.
# 위에서 정한, 드롭다운에 표시할 정렬 옵션 제공 api.
@router.get("/filters/sorts", response_model=PlayerSortFiltersResponse)
def get_player_sort_options():
    return PlayerSortFiltersResponse(sorts=MOCK_PLAYER_SORT_OPTIONS)


# Used by player list page. Supports query/position/sort + pagination.
@router.get("", response_model=PlayerListResponse)
def get_players(
    query: Optional[str] = Query(default=None),
    position: str = Query(default="ALL"),
    sort: SortOrder = Query(default="value_desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=8, ge=1),
):
    keyword = (query or "").strip().lower()
    normalized_position = position.strip().upper()

    filtered = []
    for player in MOCK_PLAYERS:
        matches_keyword = (
            not keyword
            or keyword in player.name.lower()
            or keyword in player.team.lower()
        )
        if matches_keyword and matches_position_filter(player.positions, normalized_position):
            filtered.append(player)

    sorted_players = sort_players(filtered, sort)
    total = len(sorted_players)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    safe_page = min(page, total_pages) if total_pages > 0 else 1

    start = (safe_page - 1) * limit if total_pages > 0 else 0
    end = start + limit
    paged = sorted_players[start:end]

    return PlayerListResponse(
        items=[
            PlayerListItem(
                id=p.id,
                name=p.name,
                team=p.team,
                positions=p.positions,
                valueScore=p.valueScore,
                headshotUrl=p.headshotUrl,
            )
            for p in paged
        ],
        page=safe_page,
        limit=limit,
        total=total,
        totalPages=total_pages,
    )


# Used by PlayerDetail page.
@router.get("/{player_id}", response_model=PlayerOut)
def get_player_detail(player_id: int):
    for player in MOCK_PLAYERS:
        if player.id == player_id:
            return player
    raise HTTPException(status_code=404, detail="Player not found")
