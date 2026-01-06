import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.scrapethissite.com/pages/forms/"

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_selector("table.table", timeout=10000)
        content = await page.content()
        await browser.close()
        return content

def parse_field(element, selector: str, attribute: Optional[str], field_type: str) -> Any:
    if not element:
        return None
    target = element.select_one(selector)
    if not target:
        return None
    value = target.get(attribute) if attribute else target.get_text(strip=True)
    if not value:
        return None
    if field_type == "number":
        try:
            return int(value) if '.' not in value else float(value)
        except ValueError:
            return None
    return value

def extract_team_data(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    teams = []
    containers = soup.select("tr.team")
    for container in containers:
        team = {
            "team_name": parse_field(container, "td.name", None, "string"),
            "year": parse_field(container, "td.year", None, "number"),
            "wins": parse_field(container, "td.wins", None, "number"),
            "losses": parse_field(container, "td.losses", None, "number"),
            "ot_losses": parse_field(container, "td.ot-losses", None, "number"),
            "win_percentage": parse_field(container, "td.pct", None, "number"),
            "goals_for": parse_field(container, "td.gf", None, "number"),
            "goals_against": parse_field(container, "td.ga", None, "number"),
            "goal_difference": parse_field(container, "td.diff", None, "number")
        }
        teams.append(team)
    return teams

async def scrape_hockey_team_stats() -> List[Dict[str, Any]]:
    html = await fetch_page(BASE_URL)
    soup = BeautifulSoup(html, "html.parser")
    return extract_team_data(soup)

def save_to_json(data: List[Dict[str, Any]], filename: str = "hockey_team_stats.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    data = await scrape_hockey_team_stats()
    save_to_json(data)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
