# Home page API router.
# Placeholder for future home page features.
from fastapi import APIRouter
from typing import List, Optional
from sqlalchemy import text
from orm.session import engine
from pydantic import BaseModel


router = APIRouter(prefix="/api/home", tags=["home"])


# Used by HomePage Injured Players strip + "View All" popup.
class InjuredPlayer(BaseModel):
    player_id: int
    name: str
    position: Optional[str] = None
    team: Optional[str] = None
    primary_number: Optional[str] = None
    injury_status: str
    player_value: Optional[float] = None


# Currently injured players, sorted by player_value desc.
# - Strip on HomePage uses ?limit=3
# - "View All" popup omits limit → returns full list
# - Defined BEFORE /{player_id} so the literal "/injured" path matches first.
@router.get("/injured", response_model=List[InjuredPlayer])
def list_injured(limit: Optional[int] = None):
    sql = (
        "SELECT player_id, name, position, team, primary_number, "
        "       injury_status, player_value "
        "FROM player_caching "
        "WHERE injury_status IS NOT NULL "
        "ORDER BY player_value DESC"
    )
    params: dict = {}
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    return [
        InjuredPlayer(
            player_id=r._mapping["player_id"],
            name=r._mapping["name"],
            position=r._mapping["position"],
            team=r._mapping["team"],
            primary_number=r._mapping["primary_number"],
            injury_status=r._mapping["injury_status"],
            player_value=(
                float(r._mapping["player_value"])
                if r._mapping["player_value"] is not None
                else None
            ),
        )
        for r in rows
    ]
