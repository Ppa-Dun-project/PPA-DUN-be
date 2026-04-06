# fetch_teams.py
import requests
import os
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, inspect, text, MetaData,
    Table, Column, Integer, String
)

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

API_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"

engine = create_engine(DATABASE_URL)
metadata = MetaData()


def flatten_team(team: dict) -> dict:
    return {
        "team_id": team.get("id"),
        "name": team.get("name"),
        "team_name": team.get("teamName"),
        "location_name": team.get("locationName"),
        "abbreviation": team.get("abbreviation"),
        "short_name": team.get("shortName"),
        "franchise_name": team.get("franchiseName"),
        "club_name": team.get("clubName"),
        "league_id": team.get("league", {}).get("id"),
        "league_name": team.get("league", {}).get("name"),
        "division_id": team.get("division", {}).get("id"),
        "division_name": team.get("division", {}).get("name"),
        "venue_id": team.get("venue", {}).get("id"),
        "venue_name": team.get("venue", {}).get("name"),
        "first_year_of_play": team.get("firstYearOfPlay"),
        "active": team.get("active"),
    }


def ensure_table():
    inspector = inspect(engine)
    if not inspector.has_table("mlb_team_list"):
        Table(
            "mlb_team_list", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("team_id", Integer, unique=True, index=True),
            Column("name", String(255)),
            Column("team_name", String(255)),
            Column("location_name", String(255)),
            Column("abbreviation", String(10)),
            Column("short_name", String(255)),
            Column("franchise_name", String(255)),
            Column("club_name", String(255)),
            Column("league_id", Integer),
            Column("league_name", String(255)),
            Column("division_id", Integer),
            Column("division_name", String(255)),
            Column("venue_id", Integer),
            Column("venue_name", String(255)),
            Column("first_year_of_play", String(10)),
            Column("active", Integer),
        )
        metadata.create_all(engine)
        print("테이블 생성 완료: mlb_team_list")


def fetch_and_store():
    response = requests.get(API_URL)
    response.raise_for_status()
    teams = response.json().get("teams", [])

    ensure_table()

    rows = [flatten_team(t) for t in teams]

    columns = [
        "team_id", "name", "team_name", "location_name",
        "abbreviation", "short_name", "franchise_name", "club_name",
        "league_id", "league_name", "division_id", "division_name",
        "venue_id", "venue_name", "first_year_of_play", "active"
    ]
    update_cols = [c for c in columns if c != "team_id"]
    update_clause = ", ".join([f"`{c}` = VALUES(`{c}`)" for c in update_cols])
    placeholders = ", ".join([f":{c}" for c in columns])

    sql = text(f"""
        INSERT INTO mlb_team_list ({', '.join([f'`{c}`' for c in columns])})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """)

    with engine.connect() as conn:
        conn.execute(sql, rows)
        conn.commit()

    print(f"저장/업데이트 완료: {len(rows)}팀")


if __name__ == "__main__":
    fetch_and_store()