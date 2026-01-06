import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.mcmaster.com/"

async def fetch_page(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_selector("ul.category-list", timeout=10000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def parse_category_item(item: BeautifulSoup) -> Dict[str, Any]:
    category_name = item.select_one("span.category-name")
    category_name_value = category_name.get_text(strip=True) if category_name else None

    category_url = item.select_one("a.category-tile")
    category_url_value = category_url.get("href") if category_url else None
    if category_url_value:
        category_url_value = f"{BASE_URL.rstrip('/')}/{category_url_value.lstrip('/')}"

    category_image = item.select_one("img")
    category_image_url_value = category_image.get("src") if category_image else None
    category_image_alt_value = category_image.get("alt") if category_image else None

    return {
        "category_name": category_name_value,
        "category_url": category_url_value,
        "category_image_url": category_image_url_value,
        "category_image_alt": category_image_alt_value
    }

def extract_categories(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select("ul.category-list > li")
    return [parse_category_item(container) for container in containers]

async def scrape_categories() -> List[Dict[str, Any]]:
    html = await fetch_page(BASE_URL)
    if not html:
        return []
    return extract_categories(html)

def save_to_json(data: List[Dict[str, Any]], filename: str = "categories.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    categories = await scrape_categories()
    save_to_json(categories)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
