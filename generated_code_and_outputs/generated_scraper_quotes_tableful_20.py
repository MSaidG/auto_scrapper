import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://quotes.toscrape.com/tableful"

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("table tbody tr:not(:first-child):not(:last-child)", timeout=60000)
        content = await page.content()
        await browser.close()
        return content

def parse_quote(row: BeautifulSoup) -> Dict[str, Any]:
    text_selector = "td[style*='padding-top: 2em']"
    tags_selector = "td[style*='padding-bottom: 2em'] a"

    text_elem = row.select_one(text_selector)
    text = text_elem.get_text(strip=True) if text_elem else None

    author_elem = row.select_one(text_selector)
    author = author_elem.get_text(strip=True) if author_elem else None

    tags = []
    for tag in row.select(tags_selector):
        href = tag.get("href")
        if href:
            tags.append(href)

    return {
        "text": text,
        "author": author,
        "tags": tags if tags else None
    }

def extract_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tbody tr:not(:first-child):not(:last-child)")
    quotes = []
    for row in rows:
        quote = parse_quote(row)
        quotes.append(quote)
    return quotes

async def scrape_quotes() -> List[Dict[str, Any]]:
    html = await fetch_page(BASE_URL)
    return extract_quotes(html)

def save_to_json(data: List[Dict[str, Any]], filename: str = "quotes.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    quotes = await scrape_quotes()
    save_to_json(quotes)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
