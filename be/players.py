import logging
import os
import re
from typing import List, Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
engine = create_engine(DATABASE_URL)

logger = logging.getLogger(__name__)

# Used by Player pages. This router owns player list/detail/filter APIs.
router = APIRouter(prefix="/api/players", tags=["players"])


# Used by PlayerDetail page. 선수의 상세 스탯 블록.
class PlayerStats(BaseModel):
    g: int
    pa: int
    hr: int
    ops: float
    ip: float = 0.0
    # 추가 타격 스탯
    ab: int = 0
    r: int = 0
    h: int = 0
    rbi: int = 0
    bb: int = 0
    k: int = 0
    sb: int = 0
    avg: float = 0.0
    obp: float = 0.0
    slg: float = 0.0

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
class PlayerSortOption(BaseModel):
    value: str
    label: str

# Used by PlayersToolbar sort dropdown.
class PlayerSortFiltersResponse(BaseModel):
    sorts: List[PlayerSortOption]

SortOrder = Literal["value_desc", "value_asc", "name_asc", "name_desc"]

# Used by PlayersToolbar position chips.
PLAYER_POSITION_FILTERS: List[str] = ["ALL", "C", "1B", "2B", "3B", "SS", "OF", "P", "DH"]

# Used by PlayersToolbar sort dropdown.
PLAYER_SORT_OPTIONS: List[PlayerSortOption] = [
    PlayerSortOption(value="value_desc", label="ValueScore (high -> low)"),
    PlayerSortOption(value="value_asc", label="ValueScore (low -> high)"),
    PlayerSortOption(value="name_asc", label="Name (A -> Z)"),
    PlayerSortOption(value="name_desc", label="Name (Z -> A)"),
]

# DB 포지션 → UI 필터 매핑 (LF, CF, RF → OF)
POSITION_TO_FILTER = {
    "LF": "OF", "CF": "OF", "RF": "OF",
    "TWP": "P", "IF": "SS",
}


def parse_height_to_inches(height_str: str) -> int:
    """'6\\' 0\"' 형식을 인치로 변환"""
    match = re.match(r"(\d+)'\s*(\d+)\"?", height_str or "")
    if match:
        return int(match.group(1)) * 12 + int(match.group(2))
    return 0


def build_position_filter_sql(position: str) -> str:
    """포지션 필터에 맞는 SQL WHERE 절 반환"""
    if position == "ALL":
        return ""
    if position == "P":
        return "AND p.position IN ('P', 'TWP')"
    if position == "OF":
        return "AND p.position IN ('OF', 'LF', 'CF', 'RF')"
    return "AND p.position = :position"


def build_sort_sql(sort: SortOrder) -> str:
    """정렬 기준 SQL ORDER BY 절 반환 (PPA valueScore 정렬 지원)"""
    if sort == "name_asc":
        return "ORDER BY p.full_name ASC"
    if sort == "name_desc":
        return "ORDER BY p.full_name DESC"
    if sort == "value_desc":
        return "ORDER BY COALESCE(ppa.value_score, 0) DESC, p.full_name ASC"
    if sort == "value_asc":
        return "ORDER BY COALESCE(ppa.value_score, 0) ASC, p.full_name ASC"
    return "ORDER BY p.full_name ASC"


def row_to_player_list_item(row) -> PlayerListItem:
    """DB row를 PlayerListItem 모델로 변환"""
    r = row._mapping
    raw_pos = r["position"] or "DH"
    display_pos = POSITION_TO_FILTER.get(raw_pos, raw_pos)

    return PlayerListItem(
        id=r["player_id"],
        name=r["full_name"],
        team=r["abbreviation"] or "",
        positions=[display_pos],
        valueScore=round(float(r.get("value_score") or 0), 1),
        headshotUrl=f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{r['player_id']}/headshot/67/current",
    )


def row_to_player_out(row) -> PlayerOut:
    """DB row를 PlayerOut 모델로 변환 (상세 스탯 포함)"""
    r = row._mapping
    raw_pos = r["position"] or "DH"
    display_pos = POSITION_TO_FILTER.get(raw_pos, raw_pos)

    ab = r.get("AB") or 0
    bb = r.get("BB") or 0
    hr = r.get("HR") or 0
    obp = r.get("OBP") or 0.0
    slg = r.get("SLG") or 0.0

    return PlayerOut(
        id=r["player_id"],
        name=r["full_name"],
        age=r["current_age"] or 0,
        height_in=parse_height_to_inches(r["height"]),
        weight_lb=r["weight"] or 0,
        bats=r["bat_side"] or "R",
        throws=r["pitch_hand"] or "R",
        team=r["abbreviation"] or "",
        positions=[display_pos],
        valueScore=round(float(r.get("value_score") or 0), 1),
        headshotUrl=f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{r['player_id']}/headshot/67/current",
        stats=PlayerStats(
            g=0,
            pa=ab + bb,
            hr=hr,
            ops=round(obp + slg, 3),
            ip=0.0,
            ab=ab,
            r=r.get("R") or 0,
            h=r.get("H") or 0,
            rbi=r.get("RBI") or 0,
            bb=bb,
            k=r.get("K") or 0,
            sb=r.get("SB") or 0,
            avg=round(float(r.get("AVG") or 0), 3),
            obp=round(float(obp), 3),
            slg=round(float(slg), 3),
        ),
    )


# 공통 JOIN 쿼리 베이스 (선수 + 팀 + 스탯 + PPA 스코어)
BASE_QUERY = """
    FROM mlb_players_list p
    LEFT JOIN mlb_team_list t ON p.team_id = t.team_id
    LEFT JOIN players_stats_nl_2025 s ON LOWER(s.Player) LIKE CONCAT(LOWER(p.full_name), ' %')
    LEFT JOIN player_ppa_scores ppa ON p.player_id = ppa.player_id
    WHERE p.active = 1
"""

# 리스트용 SELECT (PPA valueScore 포함)
LIST_SELECT = """
    SELECT p.player_id, p.full_name, p.current_age, p.height, p.weight,
           p.bat_side, p.pitch_hand, p.position, t.abbreviation,
           ppa.value_score
"""

# 상세용 SELECT (스탯 + PPA valueScore)
DETAIL_SELECT = """
    SELECT p.*, t.abbreviation,
           s.AB, s.R, s.H, s.HR, s.RBI, s.BB, s.K, s.SB,
           s.AVG, s.OBP, s.SLG, ppa.value_score
"""


# Used by PlayersToolbar. Returns all available player positions.
@router.get("/filters/positions", response_model=PlayerPositionFiltersResponse)
def get_player_position_filters():
    return PlayerPositionFiltersResponse(positions=PLAYER_POSITION_FILTERS)


# Used by PlayersToolbar. Returns all available sort options.
@router.get("/filters/sorts", response_model=PlayerSortFiltersResponse)
def get_player_sort_options():
    return PlayerSortFiltersResponse(sorts=PLAYER_SORT_OPTIONS)


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

    where_parts = []
    params = {}

    if keyword:
        where_parts.append(
            "(LOWER(p.full_name) LIKE :keyword OR LOWER(t.abbreviation) LIKE :keyword)"
        )
        params["keyword"] = f"%{keyword}%"

    pos_sql = build_position_filter_sql(normalized_position)
    if pos_sql and ":position" in pos_sql:
        params["position"] = normalized_position

    extra_where = (" AND " + " AND ".join(where_parts)) if where_parts else ""
    sort_sql = build_sort_sql(sort)

    count_sql = f"SELECT COUNT(*) {BASE_QUERY} {extra_where} {pos_sql}"
    with engine.connect() as conn:
        total = conn.execute(text(count_sql), params).scalar()

    total_pages = (total + limit - 1) // limit if total > 0 else 0
    safe_page = min(page, total_pages) if total_pages > 0 else 1
    offset = (safe_page - 1) * limit if total_pages > 0 else 0

    data_sql = f"""
        {LIST_SELECT}
        {BASE_QUERY} {extra_where} {pos_sql}
        {sort_sql}
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    with engine.connect() as conn:
        rows = conn.execute(text(data_sql), params).fetchall()

    return PlayerListResponse(
        items=[row_to_player_list_item(r) for r in rows],
        page=safe_page,
        limit=limit,
        total=total,
        totalPages=total_pages,
    )


# Used by PlayerDetail page.
@router.get("/{player_id}", response_model=PlayerOut)
def get_player_detail(player_id: int):
    detail_sql = f"""
        {DETAIL_SELECT}
        {BASE_QUERY} AND p.player_id = :player_id
    """
    with engine.connect() as conn:
        row = conn.execute(text(detail_sql), {"player_id": player_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Player not found")

    return row_to_player_out(row)


# 프론트엔드 PlayerInfoModal에서 호출하는 valueScore 전용 엔드포인트.
# PPA 외부 API를 통해 실제 playerValue를 계산하여 반환한다.
class PlayerValueResponse(BaseModel):
    playerId: int
    name: str
    valueScore: float


@router.get("/{player_id}/value", response_model=PlayerValueResponse)
def get_player_value(player_id: int):
    # player_ppa_scores 테이블에서 PPA API가 계산한 valueScore를 조회한다.
    ppa_sql = text("""
        SELECT player_name, value_score
        FROM player_ppa_scores
        WHERE player_id = :player_id
    """)
    with engine.connect() as conn:
        row = conn.execute(ppa_sql, {"player_id": player_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Player PPA score not found")

    return PlayerValueResponse(
        playerId=player_id,
        name=row._mapping["player_name"],
        valueScore=round(float(row._mapping["value_score"]), 1),
    )
