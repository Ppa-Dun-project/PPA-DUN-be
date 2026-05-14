# CRUD operations for draft_player_notes table.
# 한 (session_id, player_id) 조합당 메모 1개 — upsert로 덮어쓰기, 빈 문자열로 들어오면 삭제.
from datetime import datetime
from typing import List, Optional

from sqlalchemy import text

from orm.session import engine


def list_notes(session_id: int) -> List[dict]:
    """세션의 모든 메모를 반환. playerId → note 매핑용."""
    sql = text("""
        SELECT player_id, note, updated_at
        FROM draft_player_notes
        WHERE session_id = :session_id
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"session_id": session_id}).fetchall()
    return [
        {
            "playerId": r._mapping["player_id"],
            "note": r._mapping["note"],
            "updatedAt": r._mapping["updated_at"],
        }
        for r in rows
    ]


def upsert_note(session_id: int, user_id: str, player_id: str, note: str) -> dict:
    """메모 INSERT 또는 UPDATE. 항상 updated_at 갱신.
    반환값: 저장된 row의 메타데이터 (FE 상태 갱신용)."""
    now = datetime.utcnow()
    sql = text("""
        INSERT INTO draft_player_notes
            (session_id, user_id, player_id, note, created_at, updated_at)
        VALUES
            (:session_id, :user_id, :player_id, :note, :now, :now)
        ON DUPLICATE KEY UPDATE
            note = VALUES(note),
            updated_at = VALUES(updated_at)
    """)
    with engine.connect() as conn:
        conn.execute(sql, {
            "session_id": session_id,
            "user_id": user_id,
            "player_id": player_id,
            "note": note,
            "now": now,
        })
        conn.commit()
    return {"playerId": player_id, "note": note, "updatedAt": now}


def delete_note(session_id: int, player_id: str) -> None:
    """메모 삭제. 빈 문자열 저장 요청 시 호출됨."""
    sql = text("""
        DELETE FROM draft_player_notes
        WHERE session_id = :session_id AND player_id = :player_id
    """)
    with engine.connect() as conn:
        conn.execute(sql, {"session_id": session_id, "player_id": player_id})
        conn.commit()
