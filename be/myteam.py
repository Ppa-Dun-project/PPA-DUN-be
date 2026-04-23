# My Team page API router.
# Returns the user's drafted roster and budget summary.
# Filtering, sorting, and pagination are handled by the frontend.
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database.draft_store import load_draft_config
from draft import find_draft_player, get_user_picks
from security import get_current_user_id

router = APIRouter(prefix="/api/my-team", tags=["my-team"])


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
    totalBudget: int
    spentBudget: int
    remainingBudget: int


# ID를 통해 야구 선수의 드래프트 정보 + 스탯 정보 불러옴
def player_drafts_stats_collection(
    player_id: str,
    slot_pos: str,
    bid: Optional[int],
) -> Optional[MyTeamPlayerOut]:
    
    # DraftPlayerOut 타입의 객체 반환
    draft_player = find_draft_player(player_id)

    if not draft_player:
        return None

    # 벤치 선수는 원래 포지션을 괄호 안에 표시 (예: "BENCH(1B)")
    if slot_pos == "BENCH":
        original_pos = draft_player.positions[0] if draft_player.positions else "UTIL"
        position = f"BENCH({original_pos})"
    else:
        position = slot_pos

    return MyTeamPlayerOut(
        id=draft_player.id,
        name=draft_player.name,
        pos=position,
        cost=int(bid or 0),
        team=draft_player.team,
        avg=float(draft_player.avg or 0.0),
        hr=int(draft_player.hr or 0),
        rbi=int(draft_player.rbi or 0),
        sb=int(draft_player.sb or 0),
        ppaValue=float(draft_player.ppaValue),
    )

# 사용자(나) 가 드래프트 한 선수 목록과 스탯 데이터 뽑아내기
def pick_my_players(user_id: str) -> List[MyTeamPlayerOut]:
    
    # user_id 사용자가 생성한 드래프트 세션에 속한 선수들을 통째로 가져옴
    picks = get_user_picks(user_id)
    
    # 그 중에서 내 팀에 드래프트 된 선수만 골라냄
    my_picks = []
    for pick in picks:
        if pick.draftedByTeamId == "team-0":
            my_picks.append(pick)

    # 내 팀 골라낸거 깔끔하게 정렬
    mine = sorted(my_picks, key=lambda pick: pick.slotIndex)

    items: List[MyTeamPlayerOut] = []
    
    # 위에서 선수들의 드래프트 정보만 가져왔으므로, 선수별 스탯 정보가 포함된걸로 다시 가져옴
    for pick in mine:
        mapped = player_drafts_stats_collection(
            player_id=pick.playerId,
            slot_pos=pick.slotPos,
            bid=pick.bid,
        )
        if mapped:
            items.append(mapped)

    return items

# 선수별 cost 다 더해서 
def get_budget_summary(players: List[MyTeamPlayerOut], total_budget: int) -> tuple[int, int, int]:
    # 뽑은 선수별 cost 다 더해서 사용한 예산 계산
    spent = sum(player.cost for player in players)
    
    # 전체 예산에서 사용한 예산 빼서 남은 예산 계산
    remaining = max(0, total_budget - spent)
    return total_budget, spent, remaining

# 프론트엔드의 MyTeamPage.tsx 79-84에서 사용 (컴포넌트 최초 마운트 될때 실행되는 useEffect)
@router.get("/players", response_model=MyTeamPlayersResponse)
def get_my_team_players(
    current_user_id: int = Depends(get_current_user_id),
):
    user_id = str(current_user_id)

    # 내가 뽑은 선수 가져옴 (선수별 cost 이용하려고)
    source_players = pick_my_players(user_id=user_id)

    # 드래프트 설정이 없으면 총 예산 0으로 표시 (사용자가 아직 드래프트 설정을 안 한 상태)
    config = load_draft_config(user_id)
    budget = config["budget"] if config else 0

    # 예산 요약 계산
    total_budget, spent_budget, remaining_budget = get_budget_summary(
        source_players,
        budget,
    )

    # 내 선수, 전체 예산, 사용 예산, 잔여 예산
    return MyTeamPlayersResponse(
        items=source_players,
        totalBudget=total_budget,
        spentBudget=spent_budget,
        remainingBudget=remaining_budget,
    )


