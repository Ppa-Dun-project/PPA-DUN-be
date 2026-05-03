# CRUD operations for draft_config and draft_picks tables.
# Manages per-user draft settings and pick records.
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import inspect, text, MetaData, Table, Column, Integer, String, DateTime, JSON

from orm.session import engine

metadata = MetaData()


def ensure_draft_tables():
    """Creates draft_config and draft_picks tables if they don't exist."""
    inspector = inspect(engine)

    if not inspector.has_table("draft_config"):
        Table(
            "draft_config", metadata,
            Column("user_id", String(100), primary_key=True),
            Column("league_type", String(20)),
            Column("budget", Integer),
            Column("roster_players", Integer),
            Column("my_team_name", String(100)),
            Column("opp_team_names", JSON),
            Column("opponents_count", Integer),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
        )
        metadata.create_all(engine)
        print("Table created: draft_config")

    if not inspector.has_table("draft_picks"):
        Table(
            "draft_picks", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", String(100)),
            Column("player_id", String(20)),
            Column("drafted_by_team_id", String(20)),
            Column("slot_index", Integer),
            Column("slot_pos", String(10)),
            Column("bid", Integer, nullable=True),
            Column("pick_type", String(10)),
            Column("created_at", DateTime),
        )
        metadata.create_all(engine)

        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE draft_picks "
                "ADD UNIQUE INDEX uq_user_player (user_id, player_id)"
            ))
            conn.execute(text(
                "ALTER TABLE draft_picks "
                "ADD INDEX idx_user_id (user_id)"
            ))
            conn.commit()
        print("Table created: draft_picks")


# ── draft_config CRUD ──
# draft_config 테이블에 저장
def save_draft_config(
    user_id: str,
    league_type: str,
    budget: int,
    roster_players: int,
    my_team_name: str,
    opp_team_names: List[str],
    opponents_count: int,
) -> None:
    """Saves draft config (INSERT or UPDATE on duplicate)."""
    now = datetime.utcnow()
    sql = text("""
        INSERT INTO draft_config
            (user_id, league_type, budget, roster_players,
             my_team_name, opp_team_names, opponents_count,
             created_at, updated_at)
        VALUES
            (:user_id, :league_type, :budget, :roster_players,
             :my_team_name, :opp_team_names, :opponents_count,
             :now, :now)
        ON DUPLICATE KEY UPDATE
            league_type = VALUES(league_type),
            budget = VALUES(budget),
            roster_players = VALUES(roster_players),
            my_team_name = VALUES(my_team_name),
            opp_team_names = VALUES(opp_team_names),
            opponents_count = VALUES(opponents_count),
            updated_at = VALUES(updated_at)
    """)
    with engine.connect() as conn:
        conn.execute(sql, {
            "user_id": user_id,
            "league_type": league_type,
            "budget": budget,
            "roster_players": roster_players,
            "my_team_name": my_team_name,
            "opp_team_names": json.dumps(opp_team_names),
            "opponents_count": opponents_count,
            "now": now,
        })
        conn.commit()


def load_draft_config(user_id: str) -> Optional[dict]:
    """Loads a user's draft config. Returns None if not found."""
    sql = text("SELECT * FROM draft_config WHERE user_id = :user_id")
    with engine.connect() as conn:
        row = conn.execute(sql, {"user_id": user_id}).fetchone()
    if not row:
        return None
    r = row._mapping
    opp_names = r["opp_team_names"]
    if isinstance(opp_names, str):
        opp_names = json.loads(opp_names)
    return {
        "user_id": r["user_id"],
        "league_type": r["league_type"],
        "budget": r["budget"],
        "roster_players": r["roster_players"],
        "my_team_name": r["my_team_name"],
        "opp_team_names": opp_names,
        "opponents_count": r["opponents_count"],
    }


# ── draft_picks CRUD ──
# 특정 드래프트 방의 모든 팀의 모든 픽을 가져옴 (내거 상대거 전부 다)
def load_draft_picks(user_id: str) -> List[dict]:
    
    # 야구 선수 별 id, 뽑아간 팀 id 등등 개별 정보를 다 가지옴
    sql = text("""
        SELECT player_id, drafted_by_team_id, slot_index,
               slot_pos, bid, pick_type
        FROM draft_picks
        WHERE user_id = :user_id
        ORDER BY id ASC
    """)
    # with 사용으로 블록 끝나면 자동 셧다운
    with engine.connect() as conn:
        rows = conn.execute(sql, {"user_id": user_id}).fetchall()
    
    # r.mapping으로 dict 형식으로 바꿔서 반환
    # DB에서 한 row를 가져오면 SQLAlchemy가 Row 객체로 반환.
    # 이걸 간편하게 키로 접근하기 위해 dict 형식으로 변환 (_mapping)
    return [
        {
            "playerId": r._mapping["player_id"],
            "draftedByTeamId": r._mapping["drafted_by_team_id"],
            "slotIndex": r._mapping["slot_index"],
            "slotPos": r._mapping["slot_pos"],
            "bid": r._mapping["bid"],
            "type": r._mapping["pick_type"],
        }
        for r in rows
    ]


def upsert_draft_pick(
    user_id: str,
    player_id: str,
    drafted_by_team_id: str,
    slot_index: int,
    slot_pos: str,
    bid: Optional[int],
    pick_type: str,
) -> None:
    """Saves a draft pick (UPDATE on duplicate user_id+player_id)."""
    now = datetime.utcnow()
    sql = text("""
        INSERT INTO draft_picks
            (user_id, player_id, drafted_by_team_id, slot_index,
             slot_pos, bid, pick_type, created_at)
        VALUES
            (:user_id, :player_id, :drafted_by_team_id, :slot_index,
             :slot_pos, :bid, :pick_type, :now)
        ON DUPLICATE KEY UPDATE
            drafted_by_team_id = VALUES(drafted_by_team_id),
            slot_index = VALUES(slot_index),
            slot_pos = VALUES(slot_pos),
            bid = VALUES(bid),
            pick_type = VALUES(pick_type)
    """)
    with engine.connect() as conn:
        conn.execute(sql, {
            "user_id": user_id,
            "player_id": player_id,
            "drafted_by_team_id": drafted_by_team_id,
            "slot_index": slot_index,
            "slot_pos": slot_pos,
            "bid": bid,
            "pick_type": pick_type,
            "now": now,
        })
        conn.commit()


def delete_draft_pick(user_id: str, player_id: str) -> bool:
    """Deletes a specific pick. Returns True if a row was deleted."""
    sql = text("""
        DELETE FROM draft_picks
        WHERE user_id = :user_id AND player_id = :player_id
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {"user_id": user_id, "player_id": player_id})
        conn.commit()
    return result.rowcount > 0


def reset_draft(user_id: str) -> None:
    """Resets a user's entire draft (deletes config + all picks)."""
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM draft_picks WHERE user_id = :user_id"), {"user_id": user_id})
        conn.execute(text("DELETE FROM draft_config WHERE user_id = :user_id"), {"user_id": user_id})
        conn.commit()
