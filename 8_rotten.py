import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.rottentomatoes.com/browse/tv_series_browse/sort:popular"

async def fetch_page_content(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("div.flex-container[data-qa='discovery-media-list-item']", timeout=10000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def parse_show_item(item: BeautifulSoup) -> Dict[str, Any]:
    fields = {
        "title": {
            "selector": "span[data-qa='discovery-media-list-item-title']",
            "attribute": None,
            "type": "string"
        },
        "image_url": {
            "selector": "rt-img.posterImage",
            "attribute": "src",
            "type": "url"
        },
        "critics_score": {
            "selector": "rt-text[slot='criticsScore']",
            "attribute": None,
            "type": "string"
        },
        "audience_score": {
            "selector": "rt-text[slot='audienceScore']",
            "attribute": None,
            "type": "string"
        },
        "latest_episode_date": {
            "selector": "span[data-qa='discovery-media-list-item-start-date']",
            "attribute": None,
            "type": "string"
        },
        "detail_page_url": {
            "selector": "a[data-qa='discovery-media-list-item-caption']",
            "attribute": "href",
            "type": "url"
        }
    }

    show_data = {}
    for field_name, field_config in fields.items():
        selector = field_config["selector"]
        attribute = field_config["attribute"]
        element = item.select_one(selector)
        if element:
            if attribute:
                value = element.get(attribute)
            else:
                value = element.get_text(strip=True)
            show_data[field_name] = value if value else None
        else:
            show_data[field_name] = None
    return show_data

async def scrape_tv_shows() -> List[Dict[str, Any]]:
    content = await fetch_page_content(BASE_URL)
    if not content:
        return []

    soup = BeautifulSoup(content, 'html.parser')
    containers = soup.select("div.flex-container[data-qa='discovery-media-list-item']")
    shows = []
    for container in containers:
        show_data = parse_show_item(container)
        shows.append(show_data)
    return shows

async def main():
    shows = await scrape_tv_shows()
    with open('tv_shows.json', 'w', encoding='utf-8') as f:
        json.dump(shows, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
