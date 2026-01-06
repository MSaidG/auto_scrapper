import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.scrapethissite.com/pages/forms/?page_num={page_num}"

async def fetch_page_content(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_selector("table.table", timeout=10000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def parse_field(element, selector: str, attribute: Optional[str]) -> Optional[str]:
    if not element:
        return None
    target = element.select_one(selector)
    if not target:
        return None
    if attribute:
        return target.get(attribute, None)
    return target.get_text(strip=True) if target else None

def extract_number(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None

def scrape_page(content: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(content, "html.parser")
    containers = soup.select("tr.team")
    results = []
    for container in containers:
        team_name = parse_field(container, "td.name", None)
        year = extract_number(parse_field(container, "td.year", None))
        wins = extract_number(parse_field(container, "td.wins", None))
        losses = extract_number(parse_field(container, "td.losses", None))
        ot_losses = extract_number(parse_field(container, "td.ot-losses", None))
        win_percentage = extract_number(parse_field(container, "td.pct", None))
        goals_for = extract_number(parse_field(container, "td.gf", None))
        goals_against = extract_number(parse_field(container, "td.ga", None))
        goal_difference = extract_number(parse_field(container, "td.diff", None))
        results.append({
            "team_name": team_name,
            "year": year,
            "wins": wins,
            "losses": losses,
            "ot_losses": ot_losses,
            "win_percentage": win_percentage,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "goal_difference": goal_difference
        })
    return results

async def scrape_all_pages() -> List[Dict[str, Any]]:
    all_data = []
    page_num = 1
    while True:
        url = BASE_URL.format(page_num=page_num)
        content = await fetch_page_content(url)
        if not content:
            break
        data = scrape_page(content)
        if not data:
            break
        all_data.extend(data)
        page_num += 1
        await asyncio.sleep(1)
    return all_data

async def main():
    data = await scrape_all_pages()
    with open("hockey_team_stats.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
