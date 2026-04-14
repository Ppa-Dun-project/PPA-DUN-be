# Fetches MLB injury data from ESPN API/HTML and stores it in the mlb_injuries table.
import os
import logging
import requests
from datetime import datetime
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
engine = create_engine(DATABASE_URL)
metadata = MetaData()

logging.basicConfig(
    filename="scrape_injuries.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

ESPN_API_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/injuries"
ESPN_HTML_URL = "https://www.espn.com/mlb/injuries"


# ──────────────────────────────────────
# 1) Primary: ESPN JSON API
# ──────────────────────────────────────
def fetch_from_api() -> list[dict]:
    response = requests.get(ESPN_API_URL, timeout=10)
    response.raise_for_status()
    data = response.json()

    rows = []
    for team_block in data.get("injuries", []):
        team_name = team_block.get("displayName", "")

        for player in team_block.get("injuries", []):
            athlete = player.get("athlete", {})
            position = athlete.get("position", {})
            long_comment = player.get("longComment", "")
            short_comment = player.get("shortComment", "")

            rows.append({
                "player_id": str(athlete.get("id", "")),
                "player_name": athlete.get("displayName", ""),
                "position": position.get("abbreviation", "") if isinstance(position, dict) else str(position),
                "team_name": team_name,
                "team_abbr": "",
                "injury_status": player.get("status", ""),
                "injury_detail": long_comment or short_comment,
                "injury_type": short_comment,
                "injury_location": None,
                "injury_date": player.get("date", ""),
            })

    return rows


# ──────────────────────────────────────
# 2) Fallback: Selenium HTML scraping
# ──────────────────────────────────────
def fetch_from_html() -> list[dict]:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
    import time

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )

    driver = webdriver.Chrome(options=options)
    rows = []

    try:
        driver.get(ESPN_HTML_URL)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.ResponsiveTable"))
        )
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        team_sections = soup.select("div.ResponsiveTable")

        for section in team_sections:
            team_header = section.find_previous(
                ["h2", "h3", "div"],
                class_=lambda c: c and "headline" in str(c).lower()
            )
            team_name = team_header.get_text(strip=True) if team_header else "Unknown"

            table_rows = section.select("tbody tr")
            for tr in table_rows:
                cells = tr.find_all("td")
                if len(cells) >= 3:
                    name_cell = cells[0]
                    player_name = name_cell.get_text(strip=True)

                    pos_span = name_cell.find(
                        "span", class_=lambda c: c and "position" in str(c).lower()
                    )
                    position = pos_span.get_text(strip=True) if pos_span else ""

                    injury_date = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    injury_detail = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    injury_status = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                    if player_name:
                        rows.append({
                            "player_id": None,
                            "player_name": player_name,
                            "position": position,
                            "team_name": team_name,
                            "team_abbr": "",
                            "injury_status": injury_status,
                            "injury_detail": injury_detail,
                            "injury_type": None,
                            "injury_location": None,
                            "injury_date": injury_date,
                        })
    finally:
        driver.quit()

    return rows


# ──────────────────────────────────────
# DB
# ──────────────────────────────────────
def ensure_table():
    inspector = inspect(engine)
    if not inspector.has_table("mlb_injuries"):
        Table(
            "mlb_injuries", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("player_id", String(20), unique=True, index=True),
            Column("player_name", String(255)),
            Column("position", String(10)),
            Column("team_name", String(255)),
            Column("team_abbr", String(10)),
            Column("injury_status", String(50)),
            Column("injury_detail", Text),
            Column("injury_type", Text),
            Column("injury_location", String(255)),
            Column("injury_date", String(30)),
            Column("source", String(20)),
            Column("fetched_at", String(30)),
        )
        metadata.create_all(engine)
        print("Table created: mlb_injuries")


def save_to_db(rows: list[dict], source: str):
    ensure_table()

    now = datetime.now().isoformat()
    for row in rows:
        row["source"] = source
        row["fetched_at"] = now

    columns = [
        "player_id", "player_name", "position", "team_name", "team_abbr",
        "injury_status", "injury_detail", "injury_type", "injury_location",
        "injury_date", "source", "fetched_at"
    ]
    update_cols = [c for c in columns if c != "player_id"]
    update_clause = ", ".join([f"`{c}` = VALUES(`{c}`)" for c in update_cols])
    placeholders = ", ".join([f":{c}" for c in columns])

    sql = text(f"""
        INSERT INTO mlb_injuries ({', '.join([f'`{c}`' for c in columns])})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """)

    with engine.connect() as conn:
        conn.execute(sql, rows)
        conn.commit()


# ──────────────────────────────────────
# Main: API -> falls back to HTML scraping on failure
# ──────────────────────────────────────
def fetch_and_store():
    # 1st attempt: JSON API
    try:
        rows = fetch_from_api()
        if rows:
            save_to_db(rows, source="api")
            logging.info(f"API success: {len(rows)} players")
            print(f"[API] Saved/updated: {len(rows)} injured players")
            return
        else:
            raise ValueError("API responded successfully but returned empty data")

    except Exception as e:
        logging.warning(f"API failed: {e} -> switching to HTML fallback")
        print(f"[API failed] {e}")
        print("[HTML fallback] Switching to Selenium...")

    # 2nd attempt: HTML scraping
    try:
        rows = fetch_from_html()
        if rows:
            save_to_db(rows, source="html")
            logging.info(f"HTML fallback success: {len(rows)} players")
            print(f"[HTML] Saved/updated: {len(rows)} injured players")
        else:
            logging.error("HTML fallback also returned no data")
            print("[HTML] No data found")

    except Exception as e:
        logging.error(f"HTML fallback also failed: {e}")
        print(f"[HTML failed] {e}")


if __name__ == "__main__":
    fetch_and_store()