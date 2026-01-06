import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.rottentomatoes.com/browse/tv_series_browse/sort:popular"

async def fetch_page(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("div.flex-container[data-ems-id]", timeout=10000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def extract_field(element, selector: str, attribute: Optional[str]) -> Optional[str]:
    if not element:
        return None
    target = element.select_one(selector)
    if not target:
        return None
    if attribute:
        return target.get(attribute)
    return target.get_text(strip=True)

def parse_show(container) -> Dict[str, Any]:
    show = {
        "title": extract_field(container, "span.p--small[data-qa='discovery-media-list-item-title']", None),
        "url": extract_field(container, "a[data-qa='discovery-media-list-item-caption']", "href"),
        "poster_image": extract_field(container, "rt-img.posterImage", "src"),
        "critics_score": extract_field(container, "rt-text[slot='criticsScore']", None),
        "audience_score": extract_field(container, "rt-text[slot='audienceScore']", None),
        "latest_episode_date": extract_field(container, "span.smaller[data-qa='discovery-media-list-item-start-date']", None)
    }
    return {k: v for k, v in show.items() if v is not None}

def scrape_page(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select("div.flex-container[data-ems-id]")
    shows = []
    for container in containers:
        show = parse_show(container)
        if show:
            shows.append(show)
    return shows

async def scrape_all_pages() -> List[Dict[str, Any]]:
    all_shows = []
    url = BASE_URL
    while url:
        html = await fetch_page(url)
        if not html:
            break
        shows = scrape_page(html)
        if not shows:
            break
        all_shows.extend(shows)
        soup = BeautifulSoup(html, "html.parser")
        next_button = soup.select_one("a[data-qa='pagination-next']")
        url = next_button.get("href") if next_button else None
        if url and not url.startswith("http"):
            url = f"https://www.rottentomatoes.com{url}"
        await asyncio.sleep(1)
    return all_shows

def save_to_json(data: List[Dict[str, Any]], filename: str = "tv_shows.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    shows = await scrape_all_pages()
    save_to_json(shows)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
