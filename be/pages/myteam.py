# My Team page API router.
# Returns the user's drafted roster and budget summary.
# Filtering, sorting, and pagination are handled by the frontend.
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import bindparam, text as sa_text

from database.draft_store import load_draft_config
from orm.session import engine
from backend.be.pages.draft import get_user_picks
from security import get_user_id

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


# 내 팀 (team-0) 픽들에 대해 player_caching에서 한 번에 정보를 받아 MyTeamPlayerOut 리스트로 변환.
# 픽 수만큼 SQL 쿼리하던 N+1 패턴을 단일 IN 쿼리로 대체.
def pick_my_players(user_id: str) -> List[MyTeamPlayerOut]:
    picks = get_user_picks(user_id)
    mine = sorted(
        (p for p in picks if p.draftedByTeamId == "team-0"),
        key=lambda p: p.slotIndex,
    )

    if not mine:
        return []

    player_ids = [int(p.playerId) for p in mine]
    sql = sa_text("""
        SELECT player_id, position, team, avg, hr, rbi, sb, player_value, name
        FROM player_caching
        WHERE player_id IN :ids
    """).bindparams(bindparam("ids", expanding=True))

    with engine.connect() as conn:
        rows = conn.execute(sql, {"ids": player_ids}).fetchall()

    cache_by_id = {r._mapping["player_id"]: r._mapping for r in rows}

    items: List[MyTeamPlayerOut] = []
    for pick in mine:
        m = cache_by_id.get(int(pick.playerId))
        if not m:
            continue

        # BENCH 슬롯은 원래 포지션을 괄호로 표기 (예: "BENCH(OF)").
        # DH/TWP는 UTIL로 통일 (기존 동작 유지).
        if pick.slotPos == "BENCH":
            raw_pos = m["position"] or "UTIL"
            original_pos = "UTIL" if raw_pos in ("DH", "TWP") else raw_pos
            display_pos = f"BENCH({original_pos})"
        else:
            display_pos = pick.slotPos

        items.append(MyTeamPlayerOut(
            id=str(m["player_id"]),
            name=m["name"],
            pos=display_pos,
            cost=int(pick.bid or 0),
            team=m["team"] or "",
            avg=float(m["avg"] or 0.0),
            hr=int(m["hr"] or 0),
            rbi=int(m["rbi"] or 0),
            sb=int(m["sb"] or 0),
            ppaValue=float(m["player_value"] or 0.0),
        ))

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
    current_user_id: int = Depends(get_user_id),
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


