# Scrapes team depth charts from ESPN and stores them in the mlb_depth_charts table.
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import (
    Text, create_engine, inspect, text, MetaData,
    Table, Column, Integer, String
)

load_dotenv()
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# ESPN team slugs: (abbreviation, display name)
TEAMS = [
    ("ari", "Arizona Diamondbacks"),
    ("atl", "Atlanta Braves"),
    ("bal", "Baltimore Orioles"),
    ("bos", "Boston Red Sox"),
    ("chc", "Chicago Cubs"),
    ("chw", "Chicago White Sox"),
    ("cin", "Cincinnati Reds"),
    ("cle", "Cleveland Guardians"),
    ("col", "Colorado Rockies"),
    ("det", "Detroit Tigers"),
    ("hou", "Houston Astros"),
    ("kc", "Kansas City Royals"),
    ("laa", "Los Angeles Angels"),
    ("lad", "Los Angeles Dodgers"),
    ("mia", "Miami Marlins"),
    ("mil", "Milwaukee Brewers"),
    ("min", "Minnesota Twins"),
    ("nym", "New York Mets"),
    ("nyy", "New York Yankees"),
    ("ath", "Oakland Athletics"),
    ("phi", "Philadelphia Phillies"),
    ("pit", "Pittsburgh Pirates"),
    ("sd", "San Diego Padres"),
    ("sf", "San Francisco Giants"),
    ("sea", "Seattle Mariners"),
    ("stl", "St. Louis Cardinals"),
    ("tb", "Tampa Bay Rays"),
    ("tex", "Texas Rangers"),
    ("tor", "Toronto Blue Jays"),
    ("wsh", "Washington Nationals"),
]

BASE_URL = "https://www.espn.com/mlb/team/depth/_/name/{team}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

# ESPN depth chart position order (based on Table 0)
POSITIONS = ["P", "RP", "CL", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]

# Depth order column headers
DEPTH_LABELS = ["Starter", "2nd", "3rd", "4th", "5th"]


def scrape_team_depth_chart(team_slug: str, team_name: str) -> list[dict]:
    """Scrapes depth chart data for a single team from ESPN."""
    url = BASE_URL.format(team=team_slug)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    tables = soup.find_all("table")
    if len(tables) < 2:
        print(f"    [WARN] {team_slug}: table not found")
        return []

    # Table 0: position labels (P, RP, CL, C, ...)
    # Table 1: player data (Starter, 2nd, 3rd, ...)
    pos_table = tables[0]
    data_table = tables[1]

    pos_rows = pos_table.find_all("tr")
    data_rows = data_table.find_all("tr")

    # Skip first row (header)
    pos_cells = [r.find(["td", "th"]) for r in pos_rows[1:]]
    positions = [c.get_text(strip=True) for c in pos_cells if c]

    rows = []
    for row_idx, data_row in enumerate(data_rows[1:]):
        if row_idx >= len(positions):
            break
        position = positions[row_idx]

        cells = data_row.find_all("td")
        for depth_order, cell in enumerate(cells, 1):
            cell_text = cell.get_text(strip=True)
            if not cell_text or cell_text == "-":
                continue

            # Extract player name and ESPN ID from link
            link = cell.find("a", href=True)
            if not link:
                continue

            player_name = link.get_text(strip=True)
            espn_id = None
            href = link.get("href", "")
            id_match = re.search(r"/id/(\d+)", href)
            if id_match:
                espn_id = int(id_match.group(1))

            # Extract injury status
            injury_status = None
            injury_span = cell.find("span", class_="nfl-injuries-status")
            if injury_span:
                status_text = injury_span.get_text(strip=True)
                if status_text:
                    injury_status = status_text

            rows.append({
                "team": team_name,
                "position": position,
                "depth_order": depth_order,
                "player_name": player_name,
                "espn_player_id": espn_id,
                "injury_status": injury_status,
            })

    return rows


def ensure_table():
    inspector = inspect(engine)
    if not inspector.has_table("mlb_depth_charts"):
        Table(
            "mlb_depth_charts", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("team", String(255)),
            Column("position", String(10)),
            Column("depth_order", Integer),
            Column("player_name", String(255)),
            Column("espn_player_id", Integer),
            Column("injury_status", String(10)),
        )
        metadata.create_all(engine)

        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE mlb_depth_charts "
                "ADD UNIQUE INDEX uq_team_pos_order (`team`, `position`, `depth_order`)"
            ))
            conn.commit()

        print("Table created: mlb_depth_charts")
    else:
        # Add missing columns to existing table
        columns = [col["name"] for col in inspector.get_columns("mlb_depth_charts")]
        with engine.connect() as conn:
            if "espn_player_id" not in columns:
                conn.execute(text(
                    "ALTER TABLE mlb_depth_charts ADD COLUMN `espn_player_id` INT NULL"
                ))
                print("Column added: espn_player_id")
            if "injury_status" not in columns:
                conn.execute(text(
                    "ALTER TABLE mlb_depth_charts ADD COLUMN `injury_status` VARCHAR(10) NULL"
                ))
                print("Column added: injury_status")
            conn.commit()


def fetch_and_store():
    ensure_table()

    all_rows = []
    for slug, name in TEAMS:
        try:
            team_rows = scrape_team_depth_chart(slug, name)
            all_rows.extend(team_rows)
            print(f"  {name}: {len(team_rows)} players")
            time.sleep(2)
        except Exception as e:
            print(f"  {name}: failed - {e}")

    if not all_rows:
        print("No data found")
        return

    # Delete existing data and insert fresh (full refresh)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM mlb_depth_charts"))
        conn.commit()

    columns = ["team", "position", "depth_order", "player_name", "espn_player_id", "injury_status"]
    placeholders = ", ".join([f":{c}" for c in columns])

    sql = text(f"""
        INSERT INTO mlb_depth_charts ({', '.join([f'`{c}`' for c in columns])})
        VALUES ({placeholders})
    """)

    with engine.connect() as conn:
        conn.execute(sql, all_rows)
        conn.commit()

    print(f"\nSaved: {len(all_rows)} players total")


if __name__ == "__main__":
    fetch_and_store()
