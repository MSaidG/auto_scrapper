import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page

BASE_URL = "https://quotes.toscrape.com/"

async def fetch_page(browser: Browser, url: str) -> str:
    page = await browser.new_page()
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("div.quote", timeout=5000)
        content = await page.content()
        return content
    finally:
        await page.close()

def parse_quote(quote_soup: BeautifulSoup) -> Dict[str, Any]:
    text = quote_soup.select_one("span.text")
    author = quote_soup.select_one("small.author")
    author_url = quote_soup.select_one("a[href^='/author/']")
    tags = quote_soup.select("a.tag")

    return {
        "text": text.get_text(strip=True) if text else None,
        "author": author.get_text(strip=True) if author else None,
        "author_url": urljoin(BASE_URL, author_url["href"]) if author_url else None,
        "tags": [tag.get_text(strip=True) for tag in tags] if tags else [],
        "tag_urls": [urljoin(BASE_URL, tag["href"]) for tag in tags] if tags else []
    }

def extract_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    quote_containers = soup.select("div.quote")
    return [parse_quote(container) for container in quote_containers]

async def scrape_quotes() -> List[Dict[str, Any]]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            url = BASE_URL
            quotes = []
            while url:
                html = await fetch_page(browser, url)
                page_quotes = extract_quotes(html)
                quotes.extend(page_quotes)

                soup = BeautifulSoup(html, "html.parser")
                next_link = soup.select_one("li.next > a")
                url = urljoin(BASE_URL, next_link["href"]) if next_link else None

                if url:
                    await asyncio.sleep(1)
        finally:
            await browser.close()
    return quotes

def save_to_json(data: List[Dict[str, Any]], filename: str = "quotes.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    quotes = await scrape_quotes()
    save_to_json(quotes)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
