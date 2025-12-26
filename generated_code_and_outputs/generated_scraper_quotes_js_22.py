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

def parse_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    quotes = []
    for quote_div in soup.select("div.quote"):
        text_span = quote_div.select_one("span.text")
        author_span = quote_div.select_one("small.author")
        tags = [tag.get_text(strip=True) for tag in quote_div.select("div.tags a.tag")]

        quote = {
            "text": text_span.get_text(strip=True) if text_span else None,
            "author": author_span.get_text(strip=True) if author_span else None,
            "tags": tags if tags else None
        }
        quotes.append(quote)
    return quotes

async def scrape_quotes(base_url: str) -> List[Dict[str, Any]]:
    all_quotes = []
    page_number = 1
    while True:
        url = f"{base_url}page/{page_number}/"
        try:
            html = await fetch_page(url)
            quotes = parse_quotes(html)
            if not quotes:
                break
            all_quotes.extend(quotes)
            page_number += 1
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Error scraping page {page_number}: {e}")
            break
    return all_quotes

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    base_url = "https://quotes.toscrape.com/js/"
    quotes = await scrape_quotes(base_url)
    save_to_json(quotes, "quotes.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
