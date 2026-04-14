# ppa_scores.py — 전체 선수의 PPA valueScore와 recommendedBid를 계산하여 DB에 저장하는 스크립트.
# ppa_api/ppa_service.py를 통해 외부 API와 소통한다 (직접 호출하지 않음).
# 사용법: python -m database.ppa_scores
# 주기적으로 실행하여 player_ppa_scores 테이블을 갱신한다.
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
engine = create_engine(DATABASE_URL)

# ppa_api는 be/ 디렉토리에 있으므로 path 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ppa_api.ppa_service import PpaAdapterService, PpaServiceError
from ppa_api.ppa_schemas import (
    BatterBidRequestIn,
    BatterStatsIn,
    DraftContextIn,
    LeagueContextIn,
    PitcherBidRequestIn,
    PitcherStatsIn,
)


PITCHER_POSITIONS = {"P", "SP", "RP"}

DEFAULT_LEAGUE_CONTEXT = LeagueContextIn(leagueSize=12, rosterSize=23, totalBudget=3120)

DEFAULT_DRAFT_CONTEXT = DraftContextIn(
    myRemainingBudget=260,
    myRemainingRosterSpots=23,
    myPositionsFilled=[],
    draftedPlayersCount=0,
)


def _load_all_players():
    """DB에서 active 선수 전체를 AL + NL 스탯과 함께 로드한다."""
    players = []
    seen_ids = set()

    with engine.connect() as conn:
        # AL stats (이름 직접 매칭)
        al_rows = conn.execute(text("""
            SELECT p.player_id, p.full_name, p.position, t.abbreviation,
                   s.batting_average AS AVG, s.home_runs AS HR,
                   s.runs_batted_in AS RBI, s.stolen_bases AS SB
            FROM mlb_players_list p
            JOIN players_stats_al_2025 s ON p.full_name = s.player_name
            JOIN mlb_team_list t ON p.team_id = t.team_id
            WHERE p.active = 1
        """)).fetchall()

        for row in al_rows:
            pid = row._mapping["player_id"]
            if pid not in seen_ids:
                seen_ids.add(pid)
                players.append(row)

        # NL stats (Player 컬럼에서 이름 추출)
        nl_rows = conn.execute(text("""
            SELECT p.player_id, p.full_name, p.position, t.abbreviation,
                   n.AVG, n.HR, n.RBI, n.SB
            FROM (
                SELECT
                    TRIM(REGEXP_REPLACE(
                        SUBSTRING_INDEX(Player, '|', 1),
                        '(OF|SS|1B|2B|3B|C|CF|LF|RF|DH|P|U|SP|RP|IF|TWP)[, ].*$', ''
                    )) AS player_name,
                    AVG, HR, RBI, SB
                FROM players_stats_nl_2025
            ) n
            JOIN mlb_players_list p ON p.full_name = n.player_name
            JOIN mlb_team_list t ON p.team_id = t.team_id
            WHERE p.active = 1
        """)).fetchall()

        for row in nl_rows:
            pid = row._mapping["player_id"]
            if pid not in seen_ids:
                seen_ids.add(pid)
                players.append(row)

    return players


def _build_batter_bid_request(name, position, stats):
    """타자용 BatterBidRequestIn을 생성한다."""
    hr = max(0, int(stats.get("HR") or 0))
    rbi = max(0, int(stats.get("RBI") or 0))
    sb = max(0, int(stats.get("SB") or 0))
    avg = float(stats.get("AVG") or 0.250)
    if avg <= 0:
        avg = 0.250
    runs = max(0, int(round((rbi * 0.55) + (hr * 0.8) + (sb * 0.3) + 30)))
    cs = min(sb, max(0, int(round(sb * 0.25))))

    pos = position.upper()
    if pos in ("LF", "RF", "CF"):
        pos = "OF"
    if pos in ("TWP", "IF"):
        pos = "DH"

    return BatterBidRequestIn(
        playerName=name,
        playerType="batter",
        position=pos,
        stats=BatterStatsIn(AB=550, R=runs, HR=hr, RBI=rbi, SB=sb, CS=cs, AVG=avg),
        leagueContext=DEFAULT_LEAGUE_CONTEXT,
        draftContext=DEFAULT_DRAFT_CONTEXT,
    )


def _build_pitcher_bid_request(name, position):
    """투수용 PitcherBidRequestIn을 생성한다."""
    pos = "RP" if position.upper() == "RP" else "SP"
    return PitcherBidRequestIn(
        playerName=name,
        playerType="pitcher",
        position=pos,
        stats=PitcherStatsIn(IP=170.0, W=10, SV=0, K=180, ERA=3.5, WHIP=1.15),
        leagueContext=DEFAULT_LEAGUE_CONTEXT,
        draftContext=DEFAULT_DRAFT_CONTEXT,
    )


def fetch_and_store():
    """전체 선수를 PpaAdapterService를 통해 계산하고 DB에 저장한다."""
    service = PpaAdapterService.from_settings()

    rows = _load_all_players()
    print(f"총 {len(rows)}명 선수를 PPA API로 전송합니다...")

    now = datetime.utcnow()
    success = 0
    fail = 0

    upsert_sql = text("""
        INSERT INTO player_ppa_scores
            (player_id, player_name, team, position, value_score, recommended_bid, updated_at)
        VALUES
            (:player_id, :player_name, :team, :position, :value_score, :recommended_bid, :updated_at)
        ON DUPLICATE KEY UPDATE
            player_name = VALUES(player_name),
            team = VALUES(team),
            position = VALUES(position),
            value_score = VALUES(value_score),
            recommended_bid = VALUES(recommended_bid),
            updated_at = VALUES(updated_at)
    """)

    with engine.connect() as conn:
        for row in rows:
            r = row._mapping
            player_id = r["player_id"]
            name = r["full_name"]
            position = r["position"] or "DH"
            team = r["abbreviation"] or ""

            try:
                if position.upper() in PITCHER_POSITIONS:
                    payload = _build_pitcher_bid_request(name, position)
                else:
                    stats = {"AVG": r["AVG"], "HR": r["HR"], "RBI": r["RBI"], "SB": r["SB"]}
                    payload = _build_batter_bid_request(name, position, stats)

                result = service.calculate_player_bid(payload)
                value_score = float(result.playerValue)
                recommended_bid = int(result.recommendedBid)
                success += 1
            except PpaServiceError as exc:
                print(f"  FAIL: {name} — {exc.detail}")
                value_score = 0.0
                recommended_bid = 0
                fail += 1
            except Exception as exc:
                print(f"  ERROR: {name} — {exc}")
                value_score = 0.0
                recommended_bid = 0
                fail += 1

            conn.execute(upsert_sql, {
                "player_id": player_id,
                "player_name": name,
                "team": team,
                "position": position,
                "value_score": value_score,
                "recommended_bid": recommended_bid,
                "updated_at": now,
            })

        conn.commit()

    print(f"완료: 성공 {success}명, 실패 {fail}명")


if __name__ == "__main__":
    fetch_and_store()
