from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel

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

MOCK_TOP_PLAYERS: List[TopPlayerOut] = [
    TopPlayerOut(id="p1", name="Aaron Judge", team="NYY", positions=["OF"], valueScore=98.2),
    TopPlayerOut(id="p2", name="Mookie Betts", team="LAD", positions=["2B", "OF"], valueScore=95.4),
    TopPlayerOut(id="p3", name="Shohei Ohtani", team="LAD", positions=["DH"], valueScore=94.7),
    TopPlayerOut(id="p4", name="Gerrit Cole", team="NYY", positions=["P"], valueScore=92.1),
]


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
    return TopPlayersResponse(items=MOCK_TOP_PLAYERS[:limit], total=len(MOCK_TOP_PLAYERS))


# Used when frontend wants one-call bootstrap for Home page.
@router.get("/home/dashboard", response_model=HomeDashboardResponse)
def get_home_dashboard(
    news_limit: int = Query(default=3, ge=1, le=20),
    top_players_limit: int = Query(default=4, ge=1, le=50),
):
    news = build_mock_news()[:news_limit]
    top_players = MOCK_TOP_PLAYERS[:top_players_limit]
    return HomeDashboardResponse(news=news, topPlayers=top_players)
