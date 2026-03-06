from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# basically use players prefix
router = APIRouter(prefix="/api/players", tags=["players"])

# 선수 통계 정보 모델. PlayerOut의 stats 필드에 들어가는 모델
class PlayerStats(BaseModel):
    g: int
    pa: int
    hr: int
    ops: float
    ip: float = 0.0

# 선수 상세 정보 응답 모델. PlayersDetailPage 에서 사용하는 모델
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
    # [CHANGED] Frontend cards require valueScore from backend.
    valueScore: float
    stats: PlayerStats


# 선수별 개인 정보를 보낼 때 
class PlayerListItem(BaseModel):
    id: int
    name: str
    team: str
    positions: List[str]
    # [CHANGED] Include valueScore in list responses.
    valueScore: float


# PlayersPage 에서 사용하는 모델 (선수 정보 리스트 + 페이지네이션 정보)
class PlayerListResponse(BaseModel):
    items: List[PlayerListItem]
    page: int
    limit: int
    total: int
    totalPages: int


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

# 정렬 기준. 만약 프론트에서 더 추가 하는 것이 있다면 나도 여기에 추가한다.
SortOrder = Literal["value_desc", "value_asc", "name_asc", "name_desc"]


# 프론트에서 준 정렬 기준으로 정렬.
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


# GET /api/players
# 이 함수가 GET 요청을 받는다, 최종 응답이 PlayerListResponse 형태가 된다. (FastAPI가 자동으로 검증)
@router.get("", response_model=PlayerListResponse)
def get_players(
    query: Optional[str] = Query(default=None),
    position: str = Query(default="ALL"),
    sort: SortOrder = Query(default="value_desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=8, ge=1),
):
    """
    위 4개는 쿼리 파라미터로 
    GET /api/players?query=ohtani 에서 ohtani. 
    GET /api/players?position=OF 에서 OF.
    GET /api/players?sort=value_desc 에서 value_desc. 선수 정렬 기준
    페이지네이션, 1페이지부터 시작, 1 이상만 허용
    페이지네이션, 한 페이지당 선수 수, 1 이상만 허용
    """
    
    
    #검색어 정리 작업. 공백 제거, 소문자 통일
    keyword = (query or "").strip().lower()
    
    #포지션 정리 작업. 대소문자나 공백 차이 제거
    normalized_position = position.strip().upper()

    # 위에서 파라미터로 받은 조건에 맞는 선수를 걸러낼 리스트
    filtered = []
    
    # 여기는 나중에 실제 DB 쿼리로 대체될 부분
    for player in MOCK_PLAYERS:
        matches_keyword = (
            not keyword
            or keyword in player.name.lower()
            or keyword in player.team.lower()
        )
        matches_position = (
            normalized_position == "ALL"
            or normalized_position in {pos.upper() for pos in player.positions}
        )
        if matches_keyword and matches_position:
            filtered.append(player)

    # DB에서 뽑아낸 선수 명단을 sort_players 함수로 정렬. 정렬 조건도 파라미터로 받음
    sorted_players = sort_players(filtered, sort)

    # 뽑아낸 선수 명단의 페이지네이션 처리
    total = len(sorted_players)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    # 뽑아낸 선수 명단 페이지 수 보다 사용자가 요청한 페이지 수가 더 많으면, 안전하게 최대 페이지로 조정
    safe_page = min(page, total_pages) if total_pages > 0 else 1

    # 페이지에 해당하는 선수들만 잘라내는 부분 (프론트에서는 페이지가 넘어갈때마다 백엔드로 요청하는 형식)
    start = (safe_page - 1) * limit if total_pages > 0 else 0
    end = start + limit
    paged = sorted_players[start:end]

    # 페이지에 해당 하는 선수들의 정보를 items 에 담음. PlayerListItem 형태로 변환
    items = [
        PlayerListItem(
            id=p.id,
            name=p.name,
            team=p.team,
            positions=p.positions,
            valueScore=p.valueScore,
        )
        for p in paged
    ]

    # 프론트에 진짜 보내줄 데이터. 선수 정보와 페이지네이션 정보가 담김.
    return PlayerListResponse(
        items=items,
        page=safe_page,
        limit=limit,
        total=total,
        totalPages=total_pages,
    )


# GET /api/players/{player_id}
@router.get("/{player_id}", response_model=PlayerOut)
def get_player_detail(player_id: int):
    #
    for player in MOCK_PLAYERS:
        if player.id == player_id:
            return player

    raise HTTPException(status_code=404, detail="Player not found")
