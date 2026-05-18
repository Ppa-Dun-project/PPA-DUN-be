# CRUD operations for draft_sessions, draft_config, and draft_picks tables.
# 한 유저는 최대 MAX_SESSIONS_PER_USER 개의 세션을 가질 수 있고,
# 각 세션은 config 1개와 picks N개를 가짐.
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import text

from orm.session import engine

MAX_SESSIONS_PER_USER = 3


# ── draft_sessions CRUD ──

def create_session(user_id: str, name: str) -> int:
    """Creates a new session. Raises ValueError if user has reached MAX_SESSIONS_PER_USER."""
    now = datetime.utcnow()
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM draft_sessions WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).scalar()
        if count >= MAX_SESSIONS_PER_USER:
            raise ValueError(f"Maximum {MAX_SESSIONS_PER_USER} sessions per user")
        result = conn.execute(
            text("""
                INSERT INTO draft_sessions
                    (user_id, name, created_at, updated_at, last_opened_at)
                VALUES
                    (:user_id, :name, :now, :now, :now)
            """),
            {"user_id": user_id, "name": name, "now": now},
        )
        conn.commit()
        return result.lastrowid


def list_sessions(user_id: str) -> List[dict]:
    """Returns all sessions for a user, most recently opened first."""
    sql = text("""
        SELECT id, name, created_at, updated_at, last_opened_at
        FROM draft_sessions
        WHERE user_id = :user_id
        ORDER BY last_opened_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"user_id": user_id}).fetchall()
    return [
        {
            "id": r._mapping["id"],
            "name": r._mapping["name"],
            "createdAt": r._mapping["created_at"],
            "updatedAt": r._mapping["updated_at"],
            "lastOpenedAt": r._mapping["last_opened_at"],
        }
        for r in rows
    ]


def get_session(session_id: int) -> Optional[dict]:
    """Returns the full session row, or None if not found.
    엔드포인트에서 권한 체크 + 메타데이터(name 등)를 한 번에 가져올 때 사용."""
    sql = text("""
        SELECT id, user_id, name, created_at, updated_at, last_opened_at
        FROM draft_sessions
        WHERE id = :session_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"session_id": session_id}).fetchone()
    if not row:
        return None
    r = row._mapping
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "name": r["name"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "last_opened_at": r["last_opened_at"],
    }


def rename_session(session_id: int, name: str) -> None:
    now = datetime.utcnow()
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE draft_sessions
                SET name = :name, updated_at = :now
                WHERE id = :session_id
            """),
            {"session_id": session_id, "name": name, "now": now},
        )
        conn.commit()


def touch_session(session_id: int) -> None:
    """Updates last_opened_at to now. 세션 목록 정렬 기준."""
    now = datetime.utcnow()
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE draft_sessions SET last_opened_at = :now WHERE id = :session_id"),
            {"session_id": session_id, "now": now},
        )
        conn.commit()


def delete_session(session_id: int) -> None:
    """Deletes a session. CASCADE로 config와 picks는 자동 삭제됨.
    draft_player_notes는 ORM FK 제약이 없어 명시적으로 삭제한다."""
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM draft_player_notes WHERE session_id = :session_id"),
            {"session_id": session_id},
        )
        conn.execute(
            text("DELETE FROM draft_sessions WHERE id = :session_id"),
            {"session_id": session_id},
        )


# ── draft_config CRUD ──

def save_draft_config(
    session_id: int,
    user_id: str,
    league_type: str,
    budget: int,
    roster_players: int,
    my_team_name: str,
    opp_team_names: List[str],
    opponents_count: int,
    target_season: Optional[int] = None,
) -> None:
    """Saves draft config for a session (INSERT or UPDATE on duplicate session_id)."""
    now = datetime.utcnow()
    sql = text("""
        INSERT INTO draft_config
            (session_id, user_id, league_type, budget, roster_players,
             my_team_name, opp_team_names, opponents_count, target_season,
             created_at, updated_at)
        VALUES
            (:session_id, :user_id, :league_type, :budget, :roster_players,
             :my_team_name, :opp_team_names, :opponents_count, :target_season,
             :now, :now)
        ON DUPLICATE KEY UPDATE
            league_type = VALUES(league_type),
            budget = VALUES(budget),
            roster_players = VALUES(roster_players),
            my_team_name = VALUES(my_team_name),
            opp_team_names = VALUES(opp_team_names),
            opponents_count = VALUES(opponents_count),
            target_season = VALUES(target_season),
            updated_at = VALUES(updated_at)
    """)
    with engine.connect() as conn:
        conn.execute(sql, {
            "session_id": session_id,
            "user_id": user_id,
            "league_type": league_type,
            "budget": budget,
            "roster_players": roster_players,
            "my_team_name": my_team_name,
            "opp_team_names": json.dumps(opp_team_names),
            "opponents_count": opponents_count,
            "target_season": target_season,
            "now": now,
        })
        conn.commit()


def load_draft_config(session_id: int) -> Optional[dict]:
    """Loads a session's draft config. Returns None if not found."""
    sql = text("SELECT * FROM draft_config WHERE session_id = :session_id")
    with engine.connect() as conn:
        row = conn.execute(sql, {"session_id": session_id}).fetchone()
    if not row:
        return None
    r = row._mapping
    opp_names = r["opp_team_names"]
    if isinstance(opp_names, str):
        opp_names = json.loads(opp_names)
    return {
        "session_id": r["session_id"],
        "user_id": r["user_id"],
        "league_type": r["league_type"],
        "budget": r["budget"],
        "roster_players": r["roster_players"],
        "my_team_name": r["my_team_name"],
        "opp_team_names": opp_names,
        "opponents_count": r["opponents_count"],
        "target_season": r["target_season"],
    }


# ── draft_picks CRUD ──
# 특정 세션의 모든 팀의 모든 픽을 가져옴 (내거 상대거 전부 다)
def load_draft_picks(session_id: int) -> List[dict]:
    sql = text("""
        SELECT player_id, drafted_by_team_id, slot_index,
               slot_pos, bid, pick_type, kind,
               contract_code, signed_season
        FROM draft_picks
        WHERE session_id = :session_id
        ORDER BY id ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"session_id": session_id}).fetchall()

    # _mapping으로 dict 형식으로 바꿔서 반환 (SQLAlchemy Row → dict 접근)
    return [
        {
            "playerId": r._mapping["player_id"],
            "draftedByTeamId": r._mapping["drafted_by_team_id"],
            "slotIndex": r._mapping["slot_index"],
            "slotPos": r._mapping["slot_pos"],
            "bid": r._mapping["bid"],
            "type": r._mapping["pick_type"],
            "kind": r._mapping["kind"] or "main",
            "contractCode": r._mapping["contract_code"],
            "signedSeason": r._mapping["signed_season"],
        }
        for r in rows
    ]


def replace_session_picks(
    session_id: int,
    user_id: str,
    picks: List[dict],
) -> None:
    """세션의 모든 picks를 통째로 교체 (DELETE 후 bulk INSERT). 트랜잭션으로 원자적 처리.
    각 pick dict 키: player_id, drafted_by_team_id, slot_index, slot_pos, bid, pick_type,
    kind, contract_code, signed_season."""
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM draft_picks WHERE session_id = :session_id"),
            {"session_id": session_id},
        )
        if picks:
            conn.execute(
                text("""
                    INSERT INTO draft_picks
                        (session_id, user_id, player_id, drafted_by_team_id, slot_index,
                         slot_pos, bid, pick_type, kind, contract_code, signed_season,
                         created_at)
                    VALUES
                        (:session_id, :user_id, :player_id, :drafted_by_team_id, :slot_index,
                         :slot_pos, :bid, :pick_type, :kind, :contract_code, :signed_season,
                         :now)
                """),
                [
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "player_id": p["player_id"],
                        "drafted_by_team_id": p["drafted_by_team_id"],
                        "slot_index": p["slot_index"],
                        "slot_pos": p["slot_pos"],
                        "bid": p["bid"],
                        "pick_type": p["pick_type"],
                        "kind": p.get("kind") or "main",
                        "contract_code": p.get("contract_code"),
                        "signed_season": p.get("signed_season"),
                        "now": now,
                    }
                    for p in picks
                ],
            )
