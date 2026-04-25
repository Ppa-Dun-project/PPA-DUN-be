# Players page API router.
# Provides player list with search/filter/sort, player detail with full stats,
# and a per-player value endpoint that reads from the player_ppa_scores table.
# Used when the user browses the Players catalog or opens a player detail modal.
import logging
import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from database.players_lookup import get_player_by_id
from ppa_api.ppa_client import (
    ApiConfigError,
    ApiHttpError,
    ApiInvalidResponseError,
    ApiNetworkError,
    build_ppa_api_client,
)

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
engine = create_engine(DATABASE_URL)

logger = logging.getLogger(__name__)

# Used by Player pages. This router owns player list/detail/filter APIs.
router = APIRouter(prefix="/api/players", tags=["players"])


# Used by PlayerDetail page. Detailed stat block for a single player.
class PlayerStats(BaseModel):
    g: int              # 경기 수
    pa: int             # 타석 수
    hr: int             # 홈런 수
    ops: float          # OPS (출루율 + 장타율)
    ip: float = 0.0     # 투구 이닝 (투수인 경우)
    
    # Additional batting stats
    ab: int = 0         # 타수
    r: int = 0          # 득점
    h: int = 0          # 안타
    rbi: int = 0        # 타점
    bb: int = 0         # 볼넷
    k: int = 0          # 삼진
    sb: int = 0         # 도루
    cs: int = 0         # 도루 실패 (Caught Stealing)
    avg: float = 0.0    # 타율
    obp: float = 0.0    # 출루율
    slg: float = 0.0    # 장타율

# Used by PlayerDetail page. Full data for a single player.
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


class PlayerValueOut(BaseModel):
    playerId: int
    name: str
    valueScore: float


# 선수별 상세 포지션 -> 하나로 통일화 (실제 서비스에서도 그렇게 대부분 함)
POSITION_TO_FILTER = {
    "LF": "OF", "CF": "OF", "RF": "OF",
    "TWP": "P", "IF": "SS",
}


def parse_height_to_inches(height_str: str) -> int:
    """Converts height string like 6' 0\" to total inches."""
    match = re.match(r"(\d+)'\s*(\d+)\"?", height_str or "")
    if match:
        return int(match.group(1)) * 12 + int(match.group(2))
    return 0

# Converts a player row + merged stats dict into a PlayerOut model.
def player_whole_info(player_personal_info, stats: dict) -> PlayerOut:
    
    # row 객체 -> Dict 형식 (선수 신체 정보 등)
    p_info_dict = player_personal_info._mapping
    
    # position 없으면 지명 타자 자동 설정
    raw_pos = p_info_dict["position"] or "DH"
    
    # 파이썬 dict 메소드, .get(key, default)
    # key가 dict에 있으면 value 반환, 없으면 default 반환
    display_pos = POSITION_TO_FILTER.get(raw_pos, raw_pos)

    ab = stats.get("AB") or 0
    bb = stats.get("BB") or 0
    hr = stats.get("HR") or 0
    obp = stats.get("OBP") or 0.0
    slg = stats.get("SLG") or 0.0

    return PlayerOut(
        # 선수 신체 정보 뽑아낸 값
        id=p_info_dict["player_id"],
        name=p_info_dict["full_name"],
        age=p_info_dict["current_age"] or 0,
        height_in=parse_height_to_inches(p_info_dict["height"]),
        weight_lb=p_info_dict["weight"] or 0,
        bats=p_info_dict["bat_side"] or "R",
        throws=p_info_dict["pitch_hand"] or "R",
        team=p_info_dict["abbreviation"] or "",
        positions=[display_pos],
        
        # 선수 얼굴 사진
        headshotUrl=f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{p_info_dict['player_id']}/headshot/67/current",
        
        # 선수 플레이 스탯
        stats=PlayerStats(
            g=0,
            pa=ab + bb,
            hr=hr,
            ops=round(obp + slg, 3),
            ip=0.0,
            ab=ab,
            r=stats.get("R") or 0,
            h=stats.get("H") or 0,
            rbi=stats.get("RBI") or 0,
            bb=bb,
            k=stats.get("K") or 0,
            sb=stats.get("SB") or 0,
            cs=stats.get("CS") or 0,
            avg=round(float(stats.get("AVG") or 0), 3),
            obp=round(float(obp), 3),
            slg=round(float(slg), 3),
        ),
    )


# NL과 AL 스탯 행을 병합. 둘 다 있으면 counting stat은 합산하고 rate stat은 재계산,
# 하나만 있으면 그 행을 그대로, 둘 다 없으면 빈 dict 반환.
def merge_stats(nl_row, al_row) -> dict:
    # 아예 리스트에 없는 선수
    if nl_row is None and al_row is None:
        return {}
    
    # NL에만 있는 선수
    if nl_row is None:
        return dict(al_row._mapping)
    
    # AL에만 있는 선수
    if al_row is None:
        return dict(nl_row._mapping)

    # NL과 AL에 둘다 포함된 선수 (시즌 중간에 리그 이동한 경우)
    nl = nl_row._mapping
    al = al_row._mapping


    # 선수의 리그별 스탯 dict에 합산하여 저장 (NL + AL 통합과정)
    merged: dict = {}
    for col in ("AB", "R", "H", "1B", "2B", "3B", "HR", "RBI", "BB", "K", "SB", "CS"):
        merged[col] = (nl.get(col) or 0) + (al.get(col) or 0)

    ab, bb = merged["AB"], merged["BB"]

    # 타율, 출루율, 장타율은 타수/볼넷 합산 기준으로 재계산 (두 리그 합산 후 계산)
    merged["AVG"] = (merged["H"] / ab) if ab else 0.0
    merged["OBP"] = ((merged["H"] + bb) / (ab + bb)) if (ab + bb) else 0.0
    merged["SLG"] = (
        (merged["1B"] + 2 * merged["2B"] + 3 * merged["3B"] + 4 * merged["HR"]) / ab
    ) if ab else 0.0
    
    return merged


# Used by PlayerDetail page.
@router.get("/{player_id}", response_model=PlayerOut)
def get_player_detail(player_id: int):
    player_sql = """
        SELECT p.*, t.abbreviation
        FROM mlb_players_list p
        LEFT JOIN mlb_team_list t ON p.team_id = t.team_id
        WHERE p.active = 1 AND p.player_id = :player_id
    """
    stats_sql_template = """
        SELECT * FROM {table}
        WHERE LOWER(Name) LIKE CONCAT(LOWER(:full_name), ' %')
        LIMIT 1
    """

    with engine.connect() as conn:
        # SQLAlchemy가 쿼리를 실행하면 커서 형태의 결과로 반환.
        # 그 결과에서 첫 행 하나만 꺼내면 fetchone, 다 꺼내면 fetchall.
        # 선수의 개인 정보에 대해 불러옴 (신체 정보 등)
        player_personal_info = conn.execute(text(player_sql), {"player_id": player_id}).fetchone()
        
        if not player_personal_info:
            raise HTTPException(status_code=404, detail="Player not found")

        # 선수의 이름을 나중에 NL, AL DB에서 사용하여 데이터를 뽑아내기 위함
        full_name = player_personal_info._mapping["full_name"]
        
        # NL테이블에서 야구 선수 스탯 뽑아서 nl_row에 저장
        nl_row = conn.execute(
            text(stats_sql_template.format(table="players_stats_nl_2025")),
            {"full_name": full_name},
        ).fetchone()
        
        # AL테이블에서 야구 선수 스탯 뽑아서 al_row에 저장
        al_row = conn.execute(
            text(stats_sql_template.format(table="players_stats_al_2025")),
            {"full_name": full_name},
        ).fetchone()

    return player_whole_info(player_personal_info, merge_stats(nl_row, al_row))


# 외부 API의 GET /players/{name}을 호출해 valuation score를 실시간 조회.
# 응답의 id가 요청 id와 일치하는지 검증해 동명이인 케이스를 안전하게 거름.
@router.get("/{player_id}/value", response_model=PlayerValueOut)
async def get_player_value(player_id: int):
    found = get_player_by_id(str(player_id))
    if found is None:
        raise HTTPException(status_code=404, detail="Player not found")
    name, _, _ = found

    client = build_ppa_api_client()
    try:
        api_response = await client.player_by_name(name)
    except ApiHttpError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Player not found in external API")
        raise HTTPException(status_code=502, detail=f"External API error: {exc.detail}")
    except ApiNetworkError as exc:
        status = 504 if exc.timed_out else 503
        raise HTTPException(status_code=status, detail=exc.detail)
    except ApiInvalidResponseError:
        raise HTTPException(status_code=502, detail="Invalid response from external API")
    except ApiConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    player_data = api_response.get("player") or {}

    if int(player_data.get("id") or 0) != player_id:
        raise HTTPException(status_code=404, detail="Player not found")

    return PlayerValueOut(
        playerId=player_id,
        name=player_data.get("name") or name,
        valueScore=float(player_data.get("player_value") or 0.0),
    )
