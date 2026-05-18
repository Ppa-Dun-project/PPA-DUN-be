# Draft page API router.
# Handles draft configuration, player listing, pick registration/deletion (persisted to DB),
# slot assignment, and bootstrap.
# Player metadata and value come from the batter_caching table; recommended bids
# are computed in real time via the external API's POST /player/bid/id.
import logging
from datetime import datetime
from typing import Dict, List, Literal, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from contract_rollover import ContractCode
from database.draft_store import load_draft_config
from orm.session import engine
from ppa_api.ppa_client import ApiError, build_ppa_api_client
from sqlalchemy import text as sa_text

from security import get_user_id

logger = logging.getLogger(__name__)


# Used by Draft page APIs (config/filters/teams/players/picks).
router = APIRouter(prefix="/api/draft", tags=["draft"])

DraftPosition = Literal["C", "1B", "2B", "3B", "SS", "OF", "UTIL", "SP", "RP", "BENCH"]
DraftPickType = Literal["mine", "taken"]
# 마이너/택시는 메인 드래프트 전/후로 따로 등록되며 bid·포지션 자격 검사가 없음.
DraftPickKind = Literal["main", "minor", "taxi"]
PlayerType = Literal["batter", "pitcher", "two_way"]

# 선수별 드래프트 관련 정보 + 간단 개인 스탯
# 공통 요소 집합
class PlayerSummary(BaseModel):
    id: str
    name: str
    playerType: PlayerType
    positions: List[DraftPosition]
    team: str
    avg: Optional[float] = None
    hr: Optional[int] = None
    rbi: Optional[int] = None
    sb: Optional[int] = None
    ab: Optional[int] = None
    w: Optional[int] = None
    sv: Optional[int] = None
    so: Optional[int] = None
    era: Optional[float] = None
    whip: Optional[float] = None
    ip: Optional[float] = None

# 드래프트 세션 설정에 관한 값들
class DraftConfig(BaseModel):
    leagueType: str
    budget: int
    rosterPlayers: int
    myTeamName: str
    opponentsCount: int
    oppTeamNames: List[str]
    # keeper 롤오버의 기준 시즌. 옛 세션에는 없어 None일 수 있음.
    targetSeason: Optional[int] = None

# 사용자와 상대의 각 생성된 정보
class DraftTeam(BaseModel):
    id: str
    name: str
    isMine: bool

# 비로그인 사용자에게 보여줄 Summary 값의 리스트 형태
class PlayerSummaryList(BaseModel):
    items: List[PlayerSummary]


class DraftPlayerValue(BaseModel):
    playerId: str
    ppaValue: Optional[float] = None


class DraftPlayerValueList(BaseModel):
    items: List[DraftPlayerValue]


# Add 모달이 열릴 때 1명에 대해서만 외부 API로 bid를 계산해 돌려준다.
class DraftPlayerBid(BaseModel):
    playerId: str
    recommendedBid: Optional[int] = None


# 드래프트 된 야구선수의 세부 현황 및 조건
class PlayerDraftStatus(BaseModel):
    playerId: str
    draftedByTeamId: str
    # 옥션에서 선수를 지명(올린) 팀. 옛 데이터엔 없어 nullable.
    broughtUpByTeamId: Optional[str] = None
    # 마이너/택시는 포지션 슬롯이 없어 None.
    slotPos: Optional[DraftPosition] = None
    bid: Optional[int] = None
    type: DraftPickType
    # 메인/마이너/택시 보드 구분. 옛 데이터 호환을 위해 default "main".
    kind: DraftPickKind = "main"
    # Keeper 계약 코드 (영입 당시 원본). 내 픽 이외(상대팀/마이너/택시)는 None.
    contractCode: Optional[ContractCode] = None
    # 이 픽이 영입된 세션의 target_season. rollover 계산에 사용.
    signedSeason: Optional[int] = None


# 선수의 픽 상태 (어떤 팀이 픽했는지, 어떤 포지션에 배치됐는지, 가격은 얼마인지 등)
class PlayerDraftStatusIndex(PlayerDraftStatus):
    slotIndex: int

# ── Session-related models ──

class SessionSummary(BaseModel):
    id: int
    name: str
    createdAt: datetime
    updatedAt: datetime
    lastOpenedAt: datetime


class SessionList(BaseModel):
    items: List[SessionSummary]


class SessionDetail(BaseModel):
    id: int
    name: str
    config: DraftConfig
    teams: List[DraftTeam]
    picks: List[PlayerDraftStatusIndex]


class CreateSessionPayload(BaseModel):
    name: str
    config: DraftConfig
    picks: List[PlayerDraftStatusIndex]


class UpdateSessionPayload(BaseModel):
    name: str
    picks: List[PlayerDraftStatusIndex]


# /players/bid는 unsaved 드래프트도 추천가를 받아야 하므로 sessionId가 아닌 body로 직접 전달.
# 선수 1명에 대해서만 호출되므로 playerId 도 같이 받는다.
class PlayerBidPayload(BaseModel):
    playerId: str
    config: DraftConfig
    picks: List[PlayerDraftStatusIndex]


# ── Player note models ──

class PlayerNoteItem(BaseModel):
    playerId: str
    note: str
    updatedAt: datetime


class PlayerNoteList(BaseModel):
    items: List[PlayerNoteItem]


class UpdateNotePayload(BaseModel):
    note: str


# DB position -> draft position mapping
_DB_POS_TO_DRAFT: Dict[str, DraftPosition] = {
    "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
    "OF": "OF", "LF": "OF", "CF": "OF", "RF": "OF",
    "DH": "UTIL", "TWP": "UTIL", "IF": "SS",
    "P": "SP", "SP": "SP", "RP": "RP", "CL": "RP",
    "LHP": "SP", "RHP": "SP",
}

# DB-backed draft storage
from database.draft_store import (
    MAX_SESSIONS_PER_USER,
    create_session,
    list_sessions,
    get_session,
    rename_session,
    touch_session,
    delete_session,
    save_draft_config,
    load_draft_picks,
    replace_session_picks,
)
from database.note_store import (
    list_notes,
    upsert_note,
    delete_note,
)

# Clamps a number to a given range. Ensures user input stays within valid bounds.
def clamp_int(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, int(value)))


def nullable_int(value) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def nullable_float(value, digits: int = 3) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def draft_position_for(raw_position: str | None, fallback: DraftPosition) -> DraftPosition:
    return _DB_POS_TO_DRAFT.get((raw_position or "").upper(), fallback)


# Builds the list of teams for a draft room.
# opp_team_names: user-provided opponent names (auto-generated if empty)
def build_draft_teams(my_team_name: str, opp_team_names: List[str], opponents_count: int) -> List[DraftTeam]:
    # 전체 team 정보 모을 리스트 선언
    # 내 팀 정보 먼저 추가 (항상 team-0, isMine=True)
    teams: List[DraftTeam] = [
        DraftTeam(id="team-0", name=my_team_name or "My Team", isMine=True)
    ]
    
    # 상대 팀 정보 추가 (team-1, team-2, ... / isMine=False)
    for i in range(max(0, opponents_count)):
        name = opp_team_names[i] if i < len(opp_team_names) and opp_team_names[i] else f"Opponent {i + 1}"
        teams.append(DraftTeam(id=f"team-{i + 1}", name=name, isMine=False))
    
    # 전체 팀 정보 반환 (id, name, isMine)
    return teams


def normalize_draft_team_id(team_id: str) -> str:
    if team_id in {"me", "team-me"}:
        return "team-0"
    if team_id.startswith("opp") and team_id[3:].isdigit():
        return f"team-{int(team_id[3:]) + 1}"
    return team_id


def normalize_pick_team_ids(picks: List[PlayerDraftStatusIndex]) -> List[PlayerDraftStatusIndex]:
    return [
        PlayerDraftStatusIndex(
            playerId=p.playerId,
            draftedByTeamId=normalize_draft_team_id(p.draftedByTeamId),
            broughtUpByTeamId=p.broughtUpByTeamId,
            slotIndex=p.slotIndex,
            slotPos=p.slotPos,
            bid=p.bid,
            type=p.type,
            kind=p.kind,
            contractCode=p.contractCode,
            signedSeason=p.signedSeason,
        )
        for p in picks
    ]



# DB에서 드래프트 픽 목록을 불러오는 함수. session_id로 특정 세션의 모든 픽을 통째로 가져옴.
def get_session_picks(session_id: int) -> List[PlayerDraftStatusIndex]:

    # 야구 선수 별 드래프트에 관련된 개별 정보를 다 가져옴 (스탯은 제외)
    rows = load_draft_picks(session_id)
    
    # load_draft_picks 함수에서 이미 dict 형식으로 반환해옴
    # dict 형식에는 key & value
    return [
        PlayerDraftStatusIndex(
            playerId=r["playerId"],               # 선수 ID
            draftedByTeamId=normalize_draft_team_id(r["draftedByTeamId"]), # 해당 선수를 뽑은 팀 ID
            broughtUpByTeamId=r.get("broughtUpByTeamId"),  # 옥션에서 지명한 팀 (옛 행은 None)
            slotIndex=r["slotIndex"],             # 슬롯 인덱스
            slotPos=r["slotPos"],                 # 배정된 포지션 (마이너/택시는 None)
            bid=r["bid"],                         # 입찰되었던 가격
            type=r["type"],                       # 픽 유형
            kind=r.get("kind") or "main",         # 보드 구분 (옛 행은 main 폴백)
            contractCode=r.get("contractCode"),   # keeper 계약 코드 (영입 당시 원본)
            signedSeason=r.get("signedSeason"),   # 영입 세션의 target_season
        )
        for r in rows
    ]


# 드래프트 세션 normalizing
def normalized_config(
    league_type: str,
    budget: int,
    roster_players: int,
    my_team_name: str,
    opp_team_names: List[str],
    opponents_count: int,
    target_season: Optional[int] = None,
) -> Tuple[DraftConfig, List[DraftTeam]]:

    # 사용자가 최대, 최소 범위를 벗어날 경우 normalization
    normalized_budget = clamp_int(budget, 50, 600)
    normalized_roster = clamp_int(roster_players, 12, 35)
    normalized_opponents = clamp_int(opponents_count, 0, 12)

    # 전체 팀 정보 리스트
    teams = build_draft_teams(
        my_team_name=my_team_name.strip(),
        opp_team_names=opp_team_names,
        opponents_count=normalized_opponents,
    )

    # team-id, isMine, 누락 이름 자동 생성, opponents_count 기반 잘라내기 과정을 거친 상대팀 이름 리스트
    opps = [t.name for t in teams if not t.isMine]

    # 전체 드래프트 설정 정보 (config) 객체 최종 생성
    config = DraftConfig(
        leagueType=league_type,
        budget=normalized_budget,
        rosterPlayers=normalized_roster,
        myTeamName=teams[0].name,
        opponentsCount=normalized_opponents,
        oppTeamNames=opps,
        targetSeason=target_season,
    )

    # 드래프트 설정 정보 + 전체 팀 정보 반환
    return config, teams


# 세션 소유권 체크. 다른 유저의 session_id 접근 시 404 (존재 여부 노출 안 함).
# 반환된 dict는 호출자가 name 등 메타데이터로 활용 가능 — 체크 한 번으로 두 가지 일을 끝냄.
def _verify_session_owner(session_id: int, user_id: str) -> dict:
    session = get_session(session_id)
    if session is None or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# Pydantic picks → replace_session_picks가 받는 dict 형태로 변환.
def _picks_to_dicts(picks: List[PlayerDraftStatusIndex]) -> List[dict]:
    return [
        {
            "player_id": p.playerId,
            "drafted_by_team_id": normalize_draft_team_id(p.draftedByTeamId),
            "brought_up_by_team_id": p.broughtUpByTeamId,
            "slot_index": p.slotIndex,
            "slot_pos": p.slotPos,
            "bid": p.bid,
            "pick_type": p.type,
            "kind": p.kind,
            "contract_code": p.contractCode,
            "signed_season": p.signedSeason,
        }
        for p in picks
    ]



############################ 세션 관리 #############################

# 내 세션 목록. 최근에 연 순으로 정렬됨.
@router.get("/sessions", response_model=SessionList)
def list_user_sessions(current_user_id: int = Depends(get_user_id)):
    user_id = str(current_user_id)
    rows = list_sessions(user_id)
    items = [
        SessionSummary(
            id=r["id"],
            name=r["name"],
            createdAt=r["createdAt"],
            updatedAt=r["updatedAt"],
            lastOpenedAt=r["lastOpenedAt"],
        )
        for r in rows
    ]
    return SessionList(items=items)


# 새 세션 + config 생성. 이미 MAX_SESSIONS_PER_USER 개면 400.
@router.post("/sessions", response_model=SessionDetail)
def create_user_session(
    payload: CreateSessionPayload,
    current_user_id: int = Depends(get_user_id),
):
    user_id = str(current_user_id)

    config, teams = normalized_config(
        league_type=payload.config.leagueType,
        budget=payload.config.budget,
        roster_players=payload.config.rosterPlayers,
        my_team_name=payload.config.myTeamName,
        opp_team_names=payload.config.oppTeamNames,
        opponents_count=payload.config.opponentsCount,
        target_season=payload.config.targetSeason,
    )

    name = payload.name.strip() or "Untitled Draft"

    try:
        session_id = create_session(user_id=user_id, name=name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    save_draft_config(
        session_id=session_id,
        user_id=user_id,
        league_type=config.leagueType,
        budget=config.budget,
        roster_players=config.rosterPlayers,
        my_team_name=config.myTeamName,
        opp_team_names=config.oppTeamNames,
        opponents_count=config.opponentsCount,
        target_season=config.targetSeason,
    )

    picks = normalize_pick_team_ids(payload.picks)
    replace_session_picks(session_id, user_id, _picks_to_dicts(picks))

    return SessionDetail(
        id=session_id,
        name=name,
        config=config,
        teams=teams,
        picks=picks,
    )


# 특정 세션 로드. config + teams + picks 통째로 반환. last_opened_at 갱신.
@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session_detail(
    session_id: int,
    current_user_id: int = Depends(get_user_id),
):
    user_id = str(current_user_id)
    session = _verify_session_owner(session_id, user_id)

    config_row = load_draft_config(session_id)
    if config_row is None:
        # 세션은 있는데 config가 없다 = 데이터 정합성 깨짐. 정상 흐름에선 발생 안 함.
        raise HTTPException(status_code=404, detail="Session config not found")

    config, teams = normalized_config(
        league_type=config_row["league_type"],
        budget=config_row["budget"],
        roster_players=config_row["roster_players"],
        my_team_name=config_row["my_team_name"],
        opp_team_names=config_row["opp_team_names"] or [],
        opponents_count=config_row["opponents_count"],
        target_season=config_row.get("target_season"),
    )

    picks = get_session_picks(session_id)
    touch_session(session_id)

    return SessionDetail(
        id=session_id,
        name=session["name"],
        config=config,
        teams=teams,
        picks=picks,
    )


# 세션 덮어쓰기 (Save 버튼). 이름 + picks 통째로 교체. config는 lock이라 안 받음.
@router.put("/sessions/{session_id}", response_model=SessionDetail)
def update_user_session(
    session_id: int,
    payload: UpdateSessionPayload,
    current_user_id: int = Depends(get_user_id),
):
    user_id = str(current_user_id)
    _verify_session_owner(session_id, user_id)

    name = payload.name.strip() or "Untitled Draft"
    rename_session(session_id, name)
    picks = normalize_pick_team_ids(payload.picks)
    replace_session_picks(session_id, user_id, _picks_to_dicts(picks))

    config_row = load_draft_config(session_id)
    config, teams = normalized_config(
        league_type=config_row["league_type"],
        budget=config_row["budget"],
        roster_players=config_row["roster_players"],
        my_team_name=config_row["my_team_name"],
        opp_team_names=config_row["opp_team_names"] or [],
        opponents_count=config_row["opponents_count"],
        target_season=config_row.get("target_season"),
    )
    return SessionDetail(
        id=session_id,
        name=name,
        config=config,
        teams=teams,
        picks=picks,
    )


# 세션 삭제. CASCADE로 config + picks + notes 자동 삭제됨.
@router.delete("/sessions/{session_id}", response_model=dict)
def delete_user_session(
    session_id: int,
    current_user_id: int = Depends(get_user_id),
):
    user_id = str(current_user_id)
    _verify_session_owner(session_id, user_id)

    delete_session(session_id)
    return {"status": "ok", "sessionId": session_id}


############################ 선수 메모 #############################
# 세션의 모든 메모를 한 번에 반환. FE는 playerId → note dict로 변환해서 사용.
@router.get("/sessions/{session_id}/notes", response_model=PlayerNoteList)
def list_session_notes(
    session_id: int,
    current_user_id: int = Depends(get_user_id),
):
    user_id = str(current_user_id)
    _verify_session_owner(session_id, user_id)

    rows = list_notes(session_id)
    items = [
        PlayerNoteItem(
            playerId=str(r["playerId"]),
            note=r["note"],
            updatedAt=r["updatedAt"],
        )
        for r in rows
    ]
    return PlayerNoteList(items=items)


# 메모 upsert (빈 문자열이면 삭제). 한 (session, player) 조합당 메모는 항상 0 또는 1개.
@router.put("/sessions/{session_id}/notes/{player_id}", response_model=dict)
def update_session_note(
    session_id: int,
    player_id: str,
    payload: UpdateNotePayload,
    current_user_id: int = Depends(get_user_id),
):
    user_id = str(current_user_id)
    _verify_session_owner(session_id, user_id)

    note = payload.note.strip()
    if not note:
        delete_note(session_id, player_id)
        return {"status": "deleted", "playerId": player_id}

    saved = upsert_note(session_id, user_id, player_id, note)
    return {
        "status": "ok",
        "playerId": saved["playerId"],
        "note": saved["note"],
        "updatedAt": saved["updatedAt"].isoformat(),
    }


############################ 선수 데이터 #############################
# 현역 batter 전체를 player_caching에서 반환. 필터/정렬/페이지네이션은 프론트에서 처리.
# league 쿼리 파라미터로 "AL" / "NL" 지정 시 해당 리그 선수만 반환. 미지정 시 전체.
@router.get("/players", response_model=PlayerSummaryList)
def get_draft_players(league: Optional[str] = None):
    where_clause = "WHERE league = :league" if league else ""
    batter_sql = sa_text(f"""
        SELECT player_id, name, position, team, avg, hr, rbi, sb, ab, r, h, single, double, triple, bb, k, cs, obp, slg
        FROM batter_caching
        {where_clause}
    """)
    pitcher_sql = sa_text(f"""
        SELECT player_id, name, position, team, w, sv, so, era, whip, ip, l, whip, g, gs, war, fip, h, r, er, hr, bb, hbp, bf, era_plus, h9, hr9, bb9, so9, so_bb
        FROM pitcher_caching
        {where_clause}
    """)

    params = {"league": league} if league else {}
    with engine.connect() as conn:
        batter_rows = conn.execute(batter_sql, params).fetchall()
        pitcher_rows = conn.execute(pitcher_sql, params).fetchall()

    items_by_id: Dict[int, PlayerSummary] = {}

    for row in batter_rows:
        m = row._mapping
        player_id = int(m["player_id"])
        draft_pos = draft_position_for(m["position"], "UTIL")
        items_by_id[player_id] = PlayerSummary(
            id=str(m["player_id"]),
            name=m["name"] or "",
            playerType="batter",
            positions=[draft_pos],
            team=m["team"] or "",
            avg=nullable_float(m["avg"]),
            hr=nullable_int(m["hr"]),
            rbi=nullable_int(m["rbi"]),
            sb=nullable_int(m["sb"]),
            ab=nullable_int(m["ab"]),
        )

    for row in pitcher_rows:
        m = row._mapping
        player_id = int(m["player_id"])
        draft_pos = draft_position_for(m["position"], "SP")
        existing = items_by_id.get(player_id)
        if existing is not None:
            existing.playerType = "two_way"
            if draft_pos not in existing.positions:
                existing.positions.append(draft_pos)
            existing.w = nullable_int(m["w"])
            existing.sv = nullable_int(m["sv"])
            existing.so = nullable_int(m["so"])
            existing.era = nullable_float(m["era"], 2)
            existing.whip = nullable_float(m["whip"], 3)
            existing.ip = nullable_float(m["ip"], 1)
            continue

        items_by_id[player_id] = PlayerSummary(
            id=str(m["player_id"]),
            name=m["name"] or "",
            playerType="pitcher",
            positions=[draft_pos],
            team=m["team"] or "",
            w=nullable_int(m["w"]),
            sv=nullable_int(m["sv"]),
            so=nullable_int(m["so"]),
            era=nullable_float(m["era"], 2),
            whip=nullable_float(m["whip"], 3),
            ip=nullable_float(m["ip"], 1),
        )

    return PlayerSummaryList(items=list(items_by_id.values()))




########################## 선수별 PPA 가치 (DB 캐시) ##########################
# 전체 선수의 ppaValue 를 한 번에 반환. DB 캐시만 읽으므로 즉시 응답.
# bid 는 분리되어 /players/bid 가 1명씩 처리한다.
# 드래프트 세션은 로그인된 사용자만 사용 가능하므로 Depends.
@router.get("/players/value", response_model=DraftPlayerValueList)
def get_draft_player_values(
    current_user_id: int = Depends(get_user_id),  # 인증만 필요, user_id는 직접 안 씀
):
    # Local DB cache: active batters + pitchers. Two-way players are collapsed to one row.
    sql = sa_text("""
        SELECT player_id, MAX(player_value) AS player_value
        FROM (
            SELECT player_id, player_value FROM batter_caching
            UNION ALL
            SELECT player_id, player_value FROM pitcher_caching
        ) AS player_values
        GROUP BY player_id
    """)
    with engine.connect() as conn:
        cache_rows = conn.execute(sql).fetchall()

    items = [
        DraftPlayerValue(
            playerId=str(r._mapping["player_id"]),
            ppaValue=(
                float(r._mapping["player_value"])
                if r._mapping["player_value"] is not None
                else None
            ),
        )
        for r in cache_rows
    ]

    return DraftPlayerValueList(items=items)


########################## 선수 1명의 추천 입찰가 (외부 API) ##########################
# Add 모달이 열릴 때만 호출된다. 페이지 로드 시 전체 호출하던 패턴을 폐기.
# config + picks 는 league_context / draft_context 계산에 필요.
@router.post("/players/bid", response_model=DraftPlayerBid)
async def get_draft_player_bid(
    payload: PlayerBidPayload,
    current_user_id: int = Depends(get_user_id),
):
    config = payload.config
    picks = payload.picks

    # bid 계산은 메인 드래프트에만 의미가 있음 — 마이너/택시는 무료라서 budget/roster 카운트에서 제외.
    main_picks = [p for p in picks if (p.kind or "main") == "main"]
    my_picks = [p for p in main_picks if p.draftedByTeamId == "team-0"]
    my_spent = sum(p.bid or 0 for p in my_picks)
    league_context = {
        "league_size": config.opponentsCount + 1,
        "roster_size": config.rosterPlayers,
        "total_budget": config.budget,
    }
    draft_context = {
        "my_remaining_budget": max(0, config.budget - my_spent),
        "my_remaining_roster_spots": max(0, config.rosterPlayers - len(my_picks)),
        "drafted_players_count": len(main_picks),
        "my_positions_filled": [p.slotPos for p in my_picks if p.slotPos],
    }

    req_payload = {
        "player_id": int(payload.playerId),
        "league_context": league_context,
        "draft_context": draft_context,
    }

    async with build_ppa_api_client() as client:
        try:
            response = await client.player_bid(req_payload)
        except ApiError as exc:
            logger.warning("player_bid failed for player_id=%s: %s", payload.playerId, exc)
            return DraftPlayerBid(playerId=payload.playerId, recommendedBid=None)

    recommended_bid = response.get("recommended_bid")
    return DraftPlayerBid(
        playerId=payload.playerId,
        recommendedBid=int(recommended_bid) if recommended_bid is not None else None,
    )
