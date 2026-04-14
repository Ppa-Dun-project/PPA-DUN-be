import os
from datetime import datetime, timedelta, timezone
from typing import List

from dotenv import load_dotenv
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
_engine = create_engine(DATABASE_URL)

# Used by Home page sections (news/top players).
router = APIRouter(prefix="/api", tags=["home"])


# Used by HomePage latest news cards/modal.
class NewsItemOut(BaseModel):
    id: str
    title: str
    summary: str
    publishedAt: str
    url: str
    source: str | None = None


class NewsListResponse(BaseModel):
    items: List[NewsItemOut]
    total: int


# Used by home top player widgets.
class TopPlayerOut(BaseModel):
    id: str
    name: str
    team: str
    positions: List[str]
    valueScore: float


class TopPlayersResponse(BaseModel):
    items: List[TopPlayerOut]
    total: int


class HomeDashboardResponse(BaseModel):
    news: List[NewsItemOut]
    topPlayers: List[TopPlayerOut]


MOCK_NEWS_TEMPLATE = [
    (
        "n1",
        "Black Board: Weekly Fantasy Recap",
        "Top risers, biggest fallers, and one sneaky pickup you should not miss.",
        "https://example.com/news/1",
        "PPA-Dun",
        timedelta(minutes=20),
    ),
    (
        "n2",
        "Pitching Streamers to Watch",
        "3 streamers with solid matchups this week - low risk, high upside.",
        "https://example.com/news/2",
        "PPA-Dun",
        timedelta(hours=5),
    ),
    (
        "n3",
        "Injury Report: What to Do Now",
        "Quick actions to protect your roster and keep your ValueScore climbing.",
        "https://example.com/news/3",
        "PPA-Dun",
        timedelta(hours=26),
    ),
]

_DB_POS_TO_DRAFT = {
    "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
    "LF": "OF", "RF": "OF", "CF": "OF", "OF": "OF",
    "P": "SP", "SP": "SP", "RP": "RP",
    "DH": "DH", "TWP": "DH", "IF": "UTIL",
}


def get_top_players_from_db(limit: int) -> List[TopPlayerOut]:
    """player_ppa_scores 테이블에서 valueScore 상위 선수를 조회한다."""
    sql = text("""
        SELECT player_id, player_name, team, position, value_score
        FROM player_ppa_scores
        WHERE value_score > 0
        ORDER BY value_score DESC
        LIMIT :limit
    """)
    with _engine.connect() as conn:
        rows = conn.execute(sql, {"limit": limit}).fetchall()

    results: List[TopPlayerOut] = []
    for row in rows:
        r = row._mapping
        pos = _DB_POS_TO_DRAFT.get((r["position"] or "DH").upper(), "UTIL")
        results.append(TopPlayerOut(
            id=str(r["player_id"]),
            name=r["player_name"],
            team=r["team"] or "",
            positions=[pos],
            valueScore=round(float(r["value_score"]), 1),
        ))
    return results


def build_mock_news() -> List[NewsItemOut]:
    now = datetime.now(timezone.utc)
    return [
        NewsItemOut(
            id=item_id,
            title=title,
            summary=summary,
            publishedAt=(now - age_delta).isoformat(),
            url=url,
            source=source,
        )
        for item_id, title, summary, url, source, age_delta in MOCK_NEWS_TEMPLATE
    ]


# Used by HomePage TODO: GET /api/news?limit=3
@router.get("/news", response_model=NewsListResponse)
def get_news(limit: int = Query(default=3, ge=1, le=20)):
    news = build_mock_news()
    return NewsListResponse(items=news[:limit], total=len(news))


# Used by potential home ranking panel.
@router.get("/top-players", response_model=TopPlayersResponse)
def get_top_players(limit: int = Query(default=4, ge=1, le=50)):
    players = get_top_players_from_db(limit)
    return TopPlayersResponse(items=players, total=len(players))


# Used when frontend wants one-call bootstrap for Home page.
@router.get("/home/dashboard", response_model=HomeDashboardResponse)
def get_home_dashboard(
    news_limit: int = Query(default=3, ge=1, le=20),
    top_players_limit: int = Query(default=4, ge=1, le=50),
):
    news = build_mock_news()[:news_limit]
    top_players = get_top_players_from_db(top_players_limit)
    return HomeDashboardResponse(news=news, topPlayers=top_players)
