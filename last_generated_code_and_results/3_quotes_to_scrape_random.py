import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://quotes.toscrape.com/random"
OUTPUT_FILE = "quotes.json"

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("div.quote", timeout=10000)
        content = await page.content()
        await browser.close()
        return content

def parse_quote(container: BeautifulSoup) -> Dict[str, Any]:
    text = container.select_one("span.text")
    author = container.select_one("small.author")
    author_url = container.select_one("a[href^='/author/']")
    tags = container.select("a.tag")

    return {
        "text": text.get_text(strip=True) if text else None,
        "author": author.get_text(strip=True) if author else None,
        "author_url": urljoin(BASE_URL, author_url["href"]) if author_url else None,
        "tags": [tag.get_text(strip=True) for tag in tags] if tags else None,
        "tag_urls": [urljoin(BASE_URL, tag["href"]) for tag in tags] if tags else None
    }

async def scrape_quotes(num_requests: int = 10) -> List[Dict[str, Any]]:
    results = []
    for _ in range(num_requests):
        html = await fetch_page(BASE_URL)
        soup = BeautifulSoup(html, "html.parser")
        containers = soup.select("div.quote")
        for container in containers:
            results.append(parse_quote(container))
        await asyncio.sleep(1)
    return results

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    quotes = await scrape_quotes()
    save_to_json(quotes, OUTPUT_FILE)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
