import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://quotes.toscrape.com/"

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        content = await page.content()
        await browser.close()
        return content

def parse_quote(quote_soup: BeautifulSoup) -> Dict[str, Any]:
    text = quote_soup.select_one("span.text")
    author = quote_soup.select_one("small.author")
    author_url = quote_soup.select_one("a[href^='/author/']")
    tags = quote_soup.select("a.tag")

    return {
        "text": text.get_text(strip=True) if text else None,
        "author": author.get_text(strip=True) if author else None,
        "author_url": urljoin(BASE_URL, author_url["href"]) if author_url else None,
        "tags": [tag.get_text(strip=True) for tag in tags] if tags else None,
        "tag_urls": [urljoin(BASE_URL, tag["href"]) for tag in tags] if tags else None
    }

def extract_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    quote_containers = soup.select("div.quote")
    return [parse_quote(container) for container in quote_containers]

async def scrape_page(url: str) -> List[Dict[str, Any]]:
    html = await fetch_page(url)
    return extract_quotes(html)

async def scrape_all_pages() -> List[Dict[str, Any]]:
    all_quotes = []
    page_url = BASE_URL
    while page_url:
        quotes = await scrape_page(page_url)
        all_quotes.extend(quotes)
        soup = BeautifulSoup(await fetch_page(page_url), "html.parser")
        next_button = soup.select_one("li.next > a")
        page_url = urljoin(BASE_URL, next_button["href"]) if next_button else None
        await asyncio.sleep(1)
    return all_quotes

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    quotes = await scrape_all_pages()
    save_to_json(quotes, "quotes.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
