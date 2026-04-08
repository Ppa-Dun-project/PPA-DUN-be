# draft_store.py — 드래프트 설정 및 픽 데이터의 DB 저장/조회를 담당하는 모듈.
# 사용자별 드래프트 설정(draft_config)과 전체 픽(draft_picks)을 관리한다.
import json
import os
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text, MetaData, Table, Column, Integer, String, DateTime, JSON

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
engine = create_engine(DATABASE_URL)
metadata = MetaData()


def ensure_draft_tables():
    """draft_config, draft_picks 테이블이 없으면 생성한다."""
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
        print("테이블 생성 완료: draft_config")

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
        print("테이블 생성 완료: draft_picks")


# ── draft_config CRUD ──

def save_draft_config(
    user_id: str,
    league_type: str,
    budget: int,
    roster_players: int,
    my_team_name: str,
    opp_team_names: List[str],
    opponents_count: int,
) -> None:
    """드래프트 설정을 저장한다 (없으면 INSERT, 있으면 UPDATE)."""
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
    """사용자의 드래프트 설정을 조회한다. 없으면 None."""
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

def load_draft_picks(user_id: str) -> List[dict]:
    """사용자의 모든 드래프트 픽을 조회한다 (내 픽 + 상대 픽 전부)."""
    sql = text("""
        SELECT player_id, drafted_by_team_id, slot_index,
               slot_pos, bid, pick_type
        FROM draft_picks
        WHERE user_id = :user_id
        ORDER BY id ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"user_id": user_id}).fetchall()
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
    """드래프트 픽을 저장한다 (같은 user_id+player_id면 UPDATE)."""
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
    """특정 픽을 삭제한다. 삭제되었으면 True."""
    sql = text("""
        DELETE FROM draft_picks
        WHERE user_id = :user_id AND player_id = :player_id
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {"user_id": user_id, "player_id": player_id})
        conn.commit()
    return result.rowcount > 0


def reset_draft(user_id: str) -> None:
    """사용자의 드래프트를 전체 초기화한다 (설정 + 모든 픽 삭제)."""
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM draft_picks WHERE user_id = :user_id"), {"user_id": user_id})
        conn.execute(text("DELETE FROM draft_config WHERE user_id = :user_id"), {"user_id": user_id})
        conn.commit()


def save_all_picks(user_id: str, picks: List[dict]) -> None:
    """사용자의 모든 픽을 한번에 저장한다 (기존 픽 삭제 후 새로 삽입)."""
    now = datetime.utcnow()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM draft_picks WHERE user_id = :user_id"), {"user_id": user_id})

        if picks:
            sql = text("""
                INSERT INTO draft_picks
                    (user_id, player_id, drafted_by_team_id, slot_index,
                     slot_pos, bid, pick_type, created_at)
                VALUES
                    (:user_id, :player_id, :drafted_by_team_id, :slot_index,
                     :slot_pos, :bid, :pick_type, :now)
            """)
            rows = [
                {
                    "user_id": user_id,
                    "player_id": p["playerId"],
                    "drafted_by_team_id": p["draftedByTeamId"],
                    "slot_index": p["slotIndex"],
                    "slot_pos": p["slotPos"],
                    "bid": p.get("bid"),
                    "pick_type": p["type"],
                    "now": now,
                }
                for p in picks
            ]
            conn.execute(sql, rows)
        conn.commit()
