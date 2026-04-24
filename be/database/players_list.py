# Fetches MLB player roster from statsapi.mlb.com and stores it in the mlb_players_list table.
import requests
import json
from sqlalchemy import create_engine, inspect, text, MetaData, Table, Column, Integer, String, Text
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
engine = create_engine(DATABASE_URL)
metadata = MetaData()

API_URL = "https://statsapi.mlb.com/api/v1/sports/1/players?season=2025"


def flatten_player(player: dict) -> dict:
    """Flattens nested API JSON into a flat column structure."""
    return {
        "player_id": player.get("id"),
        "full_name": player.get("fullName"),
        "first_name": player.get("firstName"),
        "last_name": player.get("lastName"),
        "primary_number": player.get("primaryNumber"),
        "birth_date": player.get("birthDate"),
        "birth_city": player.get("birthCity"),
        "birth_country": player.get("birthCountry"),
        "height": player.get("height"),
        "weight": player.get("weight"),
        "current_age": player.get("currentAge"),
        "position": player.get("primaryPosition", {}).get("abbreviation"),
        "position_name": player.get("primaryPosition", {}).get("name"),
        "team_id": player.get("currentTeam", {}).get("id"),
        "team_name": player.get("currentTeam", {}).get("name"),
        "bat_side": player.get("batSide", {}).get("code"),
        "pitch_hand": player.get("pitchHand", {}).get("code"),
        "mlb_debut_date": player.get("mlbDebutDate"),
        "active": player.get("active"),
    }


def create_players_table():
    """Creates the mlb_players table if it doesn't exist."""
    inspector = inspect(engine)
    if not inspector.has_table("mlb_players"):
        table = Table(
            "mlb_players", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("player_id", Integer, index=True),
            Column("full_name", String(255)),
            Column("first_name", String(255)),
            Column("last_name", String(255)),
            Column("primary_number", String(10)),
            Column("birth_date", String(20)),
            Column("birth_city", String(255)),
            Column("birth_country", String(255)),
            Column("height", String(10)),
            Column("weight", Integer),
            Column("current_age", Integer),
            Column("position", String(10)),
            Column("position_name", String(50)),
            Column("team_id", Integer),
            Column("team_name", String(255)),
            Column("bat_side", String(5)),
            Column("pitch_hand", String(5)),
            Column("mlb_debut_date", String(20)),
            Column("active", Integer),
        )
        table.create(engine)
        print("Table created: mlb_players")


def fetch_and_store():
    """Fetches from API and stores in DB."""
    response = requests.get(API_URL)
    response.raise_for_status()
    players = response.json().get("people", [])

    create_players_table()

    metadata.reflect(bind=engine, only=["mlb_players"])
    table = metadata.tables["mlb_players"]

    rows = [flatten_player(p) for p in players]

    with engine.connect() as conn:
        conn.execute(table.insert(), rows)
        conn.commit()

    print(f"Saved: {len(rows)} players")


if __name__ == "__main__":
    fetch_and_store()