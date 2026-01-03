import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://www.kitapyurdu.com/index.php?route=product%2Fbest_sellers&list_id=729&filter_in_shelf=0&filter_in_stock=0"

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        content = await page.content()
        await browser.close()
        return content

def parse_menu_items(html: str) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select("div.menu.top.my-list > ul > li > div > ul > li")
    items = []

    for container in containers:
        item = {
            "menu_item_name": None,
            "menu_item_url": None
        }

        name_tag = container.select_one("a")
        if name_tag:
            item["menu_item_name"] = name_tag.get_text(strip=True)
            href = name_tag.get("href")
            if href:
                item["menu_item_url"] = urljoin(BASE_URL, href)

        items.append(item)

    return items

async def scrape_menu_items() -> List[Dict[str, Optional[str]]]:
    html = await fetch_page(BASE_URL)
    return parse_menu_items(html)

def save_to_json(data: List[Dict[str, Optional[str]]], filename: str = "output.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    items = await scrape_menu_items()
    save_to_json(items)
    print(f"Scraped {len(items)} menu items.")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
