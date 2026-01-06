import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.mcmaster.com/products/screws/rounded-head-screws-2~/stainless-steel-pan-head-phillips-screws~~/"

async def fetch_page(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("ul.category-list", timeout=10000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def parse_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select("ul.category-list > li")
    results = []
    for container in containers:
        item = {
            "category_name": None,
            "category_url": None,
            "category_image_url": None,
            "category_image_alt": None
        }
        name_el = container.select_one("span.category-name")
        if name_el:
            item["category_name"] = name_el.get_text(strip=True)
        url_el = container.select_one("a.category-tile")
        if url_el and url_el.has_attr("href"):
            item["category_url"] = url_el["href"]
        img_el = container.select_one("img")
        if img_el:
            if img_el.has_attr("src"):
                item["category_image_url"] = img_el["src"]
            if img_el.has_attr("alt"):
                item["category_image_alt"] = img_el["alt"]
        results.append(item)
    return results

async def scrape_category() -> List[Dict[str, Any]]:
    html = await fetch_page(BASE_URL)
    if not html:
        return []
    return parse_html(html)

async def main():
    data = await scrape_category()
    with open("scraped_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
