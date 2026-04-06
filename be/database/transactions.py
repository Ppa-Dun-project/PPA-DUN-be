# fetch_transactions.py
import requests
import os
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, inspect, text, MetaData,
    Table, Column, Integer, String, Text
)


load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

API_URL = "https://statsapi.mlb.com/api/v1/transactions?startDate=2025-01-01&endDate=2025-03-26"

engine = create_engine(DATABASE_URL)
metadata = MetaData()


def flatten_transaction(t: dict) -> dict:
    return {
        "transaction_id": t.get("id"),
        "type_code": t.get("typeCode"),
        "type_desc": t.get("typeDesc"),
        "description": t.get("description"),
        "date": t.get("date"),
        "effective_date": t.get("effectiveDate"),
        "resolution_date": t.get("resolutionDate"),
        "player_id": t.get("person", {}).get("id"),
        "player_name": t.get("person", {}).get("fullName"),
        "from_team_id": t.get("fromTeam", {}).get("id"),
        "from_team_name": t.get("fromTeam", {}).get("name"),
        "to_team_id": t.get("toTeam", {}).get("id"),
        "to_team_name": t.get("toTeam", {}).get("name"),
    }


def ensure_table():
    inspector = inspect(engine)
    if not inspector.has_table("trans_conts_status"):
        Table(
            "trans_conts_status", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("transaction_id", Integer, unique=True, index=True),
            Column("type_code", String(20)),
            Column("type_desc", String(255)),
            Column("description", Text),
            Column("date", String(30)),
            Column("effective_date", String(30)),
            Column("resolution_date", String(30)),
            Column("player_id", Integer),
            Column("player_name", String(255)),
            Column("from_team_id", Integer),
            Column("from_team_name", String(255)),
            Column("to_team_id", Integer),
            Column("to_team_name", String(255)),
        )
        metadata.create_all(engine)
        print("테이블 생성 완료: trans_conts_status")


def fetch_and_store():
    response = requests.get(API_URL)
    response.raise_for_status()
    transactions = response.json().get("transactions", [])

    ensure_table()

    rows = [flatten_transaction(t) for t in transactions]

    columns = [
        "transaction_id", "type_code", "type_desc", "description",
        "date", "effective_date", "resolution_date",
        "player_id", "player_name",
        "from_team_id", "from_team_name", "to_team_id", "to_team_name"
    ]
    update_cols = [c for c in columns if c != "transaction_id"]
    update_clause = ", ".join([f"`{c}` = VALUES(`{c}`)" for c in update_cols])
    placeholders = ", ".join([f":{c}" for c in columns])

    sql = text(f"""
        INSERT INTO trans_conts_status ({', '.join([f'`{c}`' for c in columns])})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """)

    with engine.connect() as conn:
        conn.execute(sql, rows)
        conn.commit()

    print(f"저장/업데이트 완료: {len(rows)}건")


if __name__ == "__main__":
    fetch_and_store()