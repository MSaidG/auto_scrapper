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
        await page.wait_for_selector("div.quote", state="attached")
        content = await page.content()
        await browser.close()
        return content

async def scroll_page(url: str, max_scrolls: int = 10) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("div.quote", state="attached")
        for _ in range(max_scrolls):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1000)
        content = await page.content()
        await browser.close()
        return content

def parse_quote(container: BeautifulSoup) -> Dict[str, Any]:
    text = container.select_one("span.text")
    author = container.select_one("small.author")
    tags = container.select("div.tags a.tag")

    return {
        "text": text.get_text(strip=True) if text else None,
        "author": author.get_text(strip=True) if author else None,
        "tags": [tag.get_text(strip=True) for tag in tags] if tags else None
    }

def extract_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select("div.quote")
    return [parse_quote(container) for container in containers]

async def scrape_quotes(base_url: str) -> List[Dict[str, Any]]:
    html = await scroll_page(base_url)
    return extract_quotes(html)

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    base_url = "https://quotes.toscrape.com/scroll"
    quotes = await scrape_quotes(base_url)
    save_to_json(quotes, "quotes.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
