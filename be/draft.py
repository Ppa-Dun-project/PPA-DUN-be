# Draft page API router.
# Handles draft configuration, player listing with DB-backed PPA scores,
# pick registration/deletion (persisted to DB), slot assignment, and bootstrap.
# When a user opens the Draft page, /bootstrap loads all necessary data in one call.
# Player value scores and recommended bids come from the player_ppa_scores table.
from typing import Dict, List, Literal, Optional, Set, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from database.draft_store import engine
from sqlalchemy import text as sa_text


# Used by Draft page APIs (config/filters/teams/players/picks).
router = APIRouter(prefix="/api/draft", tags=["draft"])

DraftPosition = Literal["C", "1B", "2B", "3B", "SS", "OF", "UTIL", "SP", "RP", "BENCH"]
DraftPickType = Literal["mine", "taken"]


# Used by DraftSetup/Draft page. Represents normalized draft config.
class DraftConfigOut(BaseModel):
    leagueType: str
    budget: int
    rosterPlayers: int
    myTeamName: str
    opponentsCount: int
    oppTeamNames: List[str]

class DraftTeamOut(BaseModel):
    id: str
    name: str
    isMine: bool

# 선수별 드래프트 관련 정보 + 간단 개인 스탯
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

# 선수의 픽 상태 (어떤 팀이 픽했는지, 어떤 포지션에 배치됐는지, 가격은 얼마인지 등)
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

class DraftPicksResponse(BaseModel):
    roomId: str
    items: List[DraftPickOut]

class DraftBootstrapResponse(BaseModel):
    config: DraftConfigOut
    teams: List[DraftTeamOut]
    picks: List[DraftPickOut]


# DB position -> draft position mapping
_DB_POS_TO_DRAFT: Dict[str, DraftPosition] = {
    "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
    "OF": "OF", "LF": "OF", "CF": "OF", "RF": "OF",
    "DH": "UTIL", "TWP": "UTIL", "IF": "SS",
    "P": "SP",
}

# active 칼럼: 1이면 현역, 0이면 은퇴/방출
# Avoid SELECT * / LIKE joins here: they force broader scans and break against the
# current stats schema where NL/AL tables do not share identical columns.
_DRAFT_STATS_QUERY = """
    SELECT player_name,
           SUM(HR) AS HR,
           SUM(RBI) AS RBI,
           SUM(SB) AS SB,
           SUM(H) / NULLIF(SUM(AB), 0) AS AVG
    FROM (
        SELECT TRIM(Name) AS player_name, AB, H, HR, RBI, SB
        FROM players_stats_nl_2025
        UNION ALL
        SELECT TRIM(Name) AS player_name, AB, H, HR, RBI, SB
        FROM players_stats_al_2025
    ) combined
    GROUP BY player_name
"""

_DRAFT_BASE_QUERY = f"""
    FROM mlb_players_list p
    LEFT JOIN mlb_team_list t ON p.team_id = t.team_id
    LEFT JOIN (
        {_DRAFT_STATS_QUERY}
    ) s ON s.player_name = p.full_name
    WHERE p.active = 1
"""

# DB 행 하나를 DraftPlayerOut 모델로 변환하는 함수. 
def _row_to_draft_player(row) -> DraftPlayerOut:
    r = row._mapping
    
    # 포지션 정보가 없는 선수는 DH(지명타자)로 간주
    raw_pos = r["position"] or "DH"  
    
    # DB 포지션을 드래프트 포지션으로 매핑. 위에서 DH 처리 된건 자동 UTIL로 처리
    draft_pos = _DB_POS_TO_DRAFT.get(raw_pos, "UTIL") 
    
    
    return DraftPlayerOut(
        id=str(r["player_id"]),
        name=r["full_name"],
        positions=[draft_pos],
        recommendedBid=1,
        team=r["abbreviation"] or "",
        avg=round(float(r.get("AVG") or 0), 3) or None,
        hr=int(r.get("HR") or 0) or None,
        rbi=int(r.get("RBI") or 0) or None,
        sb=int(r.get("SB") or 0) or None,
        ppaValue=0,
    )

# 아무 설정도 하지 않았을때의 기본 드래프트 세션 설정
DEFAULT_DRAFT_CONFIG = DraftConfigOut(
    leagueType="standard",
    budget=260,
    rosterPlayers=23,
    myTeamName="PPA-DUN",
    opponentsCount=0,
    oppTeamNames=[],
)


# DB-backed draft storage
from database.draft_store import (
    ensure_draft_tables,
    save_draft_config,
    load_draft_picks,
    upsert_draft_pick,
    delete_draft_pick,
    reset_draft,
)
ensure_draft_tables()

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
    # 전체 team 정보 모을 리스트 선언
    # 내 팀 정보 먼저 추가 (항상 team-0, isMine=True)
    teams: List[DraftTeamOut] = [
        DraftTeamOut(id="team-0", name=my_team_name or "My Team", isMine=True)
    ]
    
    # 상대 팀 정보 추가 (team-1, team-2, ... / isMine=False)
    for i in range(max(0, opponents_count)):
        name = opp_team_names[i] if i < len(opp_team_names) and opp_team_names[i] else f"Opponent {i + 1}"
        teams.append(DraftTeamOut(id=f"team-{i + 1}", name=name, isMine=False))
    
    # 전체 팀 정보 반환 (id, name, isMine)
    return teams



# DB에서 드래프트 픽 목록을 불러오는 함수. user_id로 특정 사용자가 생성한 드래프트 세션을 통째로 가져옴.
def get_user_picks(user_id: str) -> List[DraftPickOut]:
    
    # 야구 선수 별 드래프트에 관련된 개별 정보를 다 가져옴 (스탯은 제외)
    rows = load_draft_picks(user_id)
    
    # load_draft_picks 함수에서 이미 dict 형식으로 반환해옴
    # dict 형식에는 key & value
    # 결론적으로 이 함수의 반환 값은 내가 생성한 타입 (DraftPickOut)으로 구성된 리스트
    return [
        DraftPickOut(
            playerId=r["playerId"],               # 선수 ID
            draftedByTeamId=r["draftedByTeamId"], # 해당 선수를 뽑은 팀 ID
            slotIndex=r["slotIndex"],             # 슬롯 인덱스
            slotPos=r["slotPos"],                 # 배정된 포지션
            bid=r["bid"],                         # 입찰되었던 가격
            type=r["type"],                       # 픽 유형
        )
        for r in rows
    ]

# Looks up a single player by player_id from the database.
def find_draft_player(player_id: str) -> Optional[DraftPlayerOut]:    
    # :player_id는 플레이스홀더로, 실제 값은 그 아래 execute()에서 전달
    # 한 선수의 스탯 부터 모든 정보를 한번에 다 모아서 갖고옴
    sql = sa_text(f"""
        SELECT p.player_id, p.full_name, p.position, t.abbreviation,
               s.AVG, s.HR, s.RBI, s.SB
        {_DRAFT_BASE_QUERY} AND p.player_id = :player_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"player_id": int(player_id)}).fetchone()
    
    if not row:
        return None
    
    
    return _row_to_draft_player(row)


def find_available_slot_index(
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



# 드래프트 세션 normalizing
def normalized_config(
    league_type: Optional[str],
    budget: Optional[int],
    roster_players: Optional[int],
    my_team_name: Optional[str],
    opp_team_names: List[str],
    opponents_count: Optional[int],
) -> Tuple[DraftConfigOut, List[DraftTeamOut]]:

    # 사용자가 최대, 최소 범위를 벗어날 경우 normalization
    normalized_budget = clamp_int(budget, 50, 600, DEFAULT_DRAFT_CONFIG.budget)
    normalized_roster = clamp_int(roster_players, 12, 35, DEFAULT_DRAFT_CONFIG.rosterPlayers)
    normalized_opponents = clamp_int(opponents_count, 0, 12, DEFAULT_DRAFT_CONFIG.opponentsCount)

    # 전체 팀 정보 리스트
    teams = build_draft_teams(
        my_team_name=(my_team_name or "").strip() or DEFAULT_DRAFT_CONFIG.myTeamName,
        opp_team_names=opp_team_names,
        opponents_count=normalized_opponents,
    )
    
    # team-id, isMine, 누락 이름 자동 생성, opponents_count 기반 잘라내기 과정을 거친 상대팀 이름 리스트
    opps = [t.name for t in teams if not t.isMine]

    # 전체 드래프트 설정 정보 (config) 객체 최종 생성
    config = DraftConfigOut(
        leagueType=league_type or DEFAULT_DRAFT_CONFIG.leagueType,
        budget=normalized_budget,
        rosterPlayers=normalized_roster,
        myTeamName=teams[0].name,
        opponentsCount=normalized_opponents,
        oppTeamNames=opps,
    )
    
    # 드래프트 설정 정보 + 전체 팀 정보 반환
    return config, teams







############################ 드래프트 현황 #############################
# 드래프트 페이지 초기 마운트시 프론트가 가장 먼저 호출하는 통합 엔드포인트
@router.get("/bootstrap", response_model=DraftBootstrapResponse)
def get_draft_bootstrap(
    league_type: Optional[str] = Query(default=None, alias="leagueType"),
    budget: Optional[int] = Query(default=None),
    roster_players: Optional[int] = Query(default=None, alias="rosterPlayers"),
    my_team_name: Optional[str] = Query(default=None, alias="myTeamName"),
    opp_team_names_raw: str = Query(default="", alias="oppTeamNames"),
    opponents_count: Optional[int] = Query(default=None, alias="opponentsCount"),
    user_id: str = Query(default="default", alias="userId"),
):
    
    # 프론트에서 보낸 상대팀 이름 뽑아내기
    opp_team_names: List[str] = []
    for name in opp_team_names_raw.split(","):
        # 문자열 앞뒤 공백 제거
        trimmed = name.strip()
        if trimmed:
            opp_team_names.append(trimmed)
    
    config, teams = normalized_config(
        league_type=league_type,
        budget=budget,
        roster_players=roster_players,
        my_team_name=my_team_name,
        opp_team_names=opp_team_names,
        opponents_count=opponents_count,
    )

    # DB의 draft_config 테이블에 드래프트 설정 정보 저장
    save_draft_config(
        user_id=user_id,
        league_type=config.leagueType,
        budget=config.budget,
        roster_players=config.rosterPlayers,
        my_team_name=config.myTeamName,
        opp_team_names=config.oppTeamNames,
        opponents_count=config.opponentsCount,
    )

    # 사용자가 생성한 드래프트 세션의 현황 불러오기
    # 혹여나 사용자가 저번에 하다가 나간 드래프트 세션이 있는 경우.
    picks = get_user_picks(user_id)
    
    
    return DraftBootstrapResponse(
        config=config,
        teams=teams,
        picks=picks,
    )


############################ 선수 데이터 #############################
# 현역 선수 전체를 반환. 필터/정렬/페이지네이션은 프론트에서 처리.
@router.get("/players", response_model=DraftPlayerListResponse)
def get_draft_players():
    data_sql = sa_text(f"""
        SELECT p.player_id, p.full_name, p.position, t.abbreviation,
               s.AVG, s.HR, s.RBI, s.SB
        {_DRAFT_BASE_QUERY}
    """)
    with engine.connect() as conn:
        rows = conn.execute(data_sql).fetchall()

    items = [_row_to_draft_player(r) for r in rows]
    return DraftPlayerListResponse(items=items)


########################## 드래프트에서 선수 픽 등록/수정 (Add/Taken) ##########################
# 등록되어있는 선수 remove 기능 만들건지? 현재로서는 add/taken에서만 호출됨
@router.post("/picks", response_model=DraftPicksResponse)
def upsert_draft_pick_endpoint(
    payload: DraftPickUpsertIn,
    user_id: str = Query(default="default", alias="userId"),
    roster_players: Optional[int] = Query(default=None, alias="rosterPlayers"),
):
    # 선수의 요약된 스탯 정보를 불러옴
    player = find_draft_player(payload.playerId)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # 현재 드래프트 픽 상태를 모두 불러옴 (내 픽, 상대 픽 전부 다)
    picks = get_user_picks(user_id)
    
    
    # Upsert 지원: 같은 선수를 다시 픽하는 경우, 기존 픽을 제외한 목록으로 슬롯 계산.
    # next_picks: player_id에 해당하는 선수 제외 나머지 선수들 리스트
    next_picks: List[DraftPickOut] = []
    for pick in picks:
        # DB에서 불러온 id vs 프론트에서 보낸 id
        # id가 다른 경우에만 넣어라 -> 동일한 선수는 들어가지 않도록 -> 한 선수의 포지션을 바꾸는 경우
        if pick.playerId != payload.playerId:
            next_picks.append(pick)
    
    # roster_players가 None/0/음수이면 기본값으로 폴백.
    # 슬라이스가 리스트 길이를 자연스럽게 상한으로 처리하므로 상한 clamp는 불필요.
    if roster_players and roster_players > 0:
        roster_slots = roster_players
    else:
        roster_slots = DEFAULT_DRAFT_CONFIG.rosterPlayers

    # roster 야구 선수 수에 따라 슬롯 템플릿 자름. 만약 23명보다 적다면 뒤에 있는 BENCH 슬롯부터 사라짐.
    slot_template = SLOT_TEMPLATE_BASE[:roster_slots]
    
    
    # 이 팀(draftedByTeamId)이 이미 차지한 슬롯 번호들을 집합으로 모음.
    occupied: Set[int] = set()
    
    # player_id에 해당하는 선수 제외 나머지 선수들이 차지하고 있는 슬롯 인덱스 뽑아내기
    for pick in next_picks:
        if pick.draftedByTeamId == payload.draftedByTeamId:
            occupied.add(pick.slotIndex)
    
    
    ########################### 드래프트 한 선수 위치 변경 ############################
    # 현재는 그냥 가장 먼저 나오는 빈 슬롯에 배치하는 걸로 되어 있음. (포지션 규칙 없이)
    resolved_slot_index = find_available_slot_index(
        payload.slotPos,
        slot_template,
        occupied,
    )
    
    # 남은 자리가 없는 경우
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

    all_picks = get_user_picks(user_id)
    return DraftPicksResponse(roomId=user_id, items=all_picks)


############################### 야구 선수 드래프트에서 삭제 (픽 취소) ###############################
@router.delete("/picks/{player_id}", response_model=DraftPicksResponse)
def delete_draft_pick_endpoint(
    player_id: str,
    user_id: str = Query(default="default", alias="userId"),
):
    deleted = delete_draft_pick(user_id, player_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Pick not found")

    all_picks = get_user_picks(user_id)
    return DraftPicksResponse(roomId=user_id, items=all_picks)




# 추후 드래프트 리셋 기능을 만들게 되면 사용.
@router.delete("/reset", response_model=dict)
def reset_draft_endpoint(
    user_id: str = Query(default="default", alias="userId"),
):
    reset_draft(user_id)
    return {"status": "ok", "userId": user_id}
