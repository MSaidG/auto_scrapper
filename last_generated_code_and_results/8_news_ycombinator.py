import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://news.ycombinator.com/"

async def fetch_page(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("tr.athing.submission", timeout=10000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def parse_story(story_row: BeautifulSoup) -> Dict[str, Any]:
    def safe_extract(selector: str, attribute: Optional[str] = None, default: Any = None) -> Any:
        element = story_row.select_one(selector)
        if not element:
            return default
        if attribute:
            value = element.get(attribute, default)
            return value if value else default
        text = element.get_text(strip=True)
        return text if text else default

    rank = safe_extract("span.rank")
    title = safe_extract("a[href^='http']")
    url = safe_extract("a[href^='http']", "href")
    points = safe_extract("span.score")
    author = safe_extract("a.hnuser")
    time_ago = safe_extract("span.age a")
    comments_count = safe_extract("a[href^='item?id=']:last-of-type")
    domain = safe_extract("span.sitestr")

    def parse_number(value: str) -> Optional[int]:
        if not value:
            return None
        try:
            return int(value.split()[0])
        except (ValueError, AttributeError):
            return None

    return {
        "rank": parse_number(rank),
        "title": title,
        "url": url,
        "points": parse_number(points),
        "author": author,
        "time_ago": time_ago,
        "comments_count": parse_number(comments_count),
        "domain": domain
    }

def scrape_stories(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    stories = []
    for row in soup.select("tr.athing.submission"):
        story = parse_story(row)
        stories.append(story)
    return stories

async def scrape_hacker_news() -> List[Dict[str, Any]]:
    html = await fetch_page(BASE_URL)
    if not html:
        return []
    return scrape_stories(html)

def save_to_json(data: List[Dict[str, Any]], filename: str = "hacker_news_stories.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    stories = await scrape_hacker_news()
    save_to_json(stories)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
