import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("table", state="attached")
        content = await page.content()
        await browser.close()
        return content

def parse_quote(row: BeautifulSoup) -> Dict[str, Any]:
    text_td = row.select_one("td[style='padding-top: 2em;']")
    text = text_td.get_text(strip=True) if text_td else None

    author_td = row.select_one("td[style='padding-top: 2em;']")
    author = author_td.get_text(strip=True) if author_td else None

    tags = []
    tag_links = row.select("td[style='padding-bottom: 2em;'] a")
    for link in tag_links:
        href = link.get("href")
        if href:
            tags.append(href)

    return {
        "text": text,
        "author": author,
        "tags": tags if tags else None
    }

def extract_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr[style='border-bottom: 0px; ']")
    quotes = []
    for row in rows:
        quote = parse_quote(row)
        quotes.append(quote)
    return quotes

async def scrape_quotes(base_url: str) -> List[Dict[str, Any]]:
    html = await fetch_page(base_url)
    quotes = extract_quotes(html)
    return quotes

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    base_url = "https://quotes.toscrape.com/tableful/"
    quotes = await scrape_quotes(base_url)
    save_to_json(quotes, "quotes.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
