import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=10000)
        content = await page.content()
        await browser.close()
        return content

def parse_quote(quote_soup: BeautifulSoup) -> Dict[str, Any]:
    def safe_extract(selector: str, attribute: Optional[str] = None) -> Optional[str]:
        element = quote_soup.select_one(selector)
        if not element:
            return None
        if attribute:
            return element.get(attribute)
        return element.get_text(strip=True)

    text = safe_extract("span.text")
    author = safe_extract("small.author")
    author_url = safe_extract("a[href^='/author/']", "href")
    tags = [tag.get_text(strip=True) for tag in quote_soup.select("a.tag")]
    tag_urls = [tag.get("href") for tag in quote_soup.select("a.tag")]

    return {
        "text": text,
        "author": author,
        "author_url": author_url,
        "tags": tags,
        "tag_urls": tag_urls
    }

def extract_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    quotes = []
    for quote in soup.select("div.quote"):
        quotes.append(parse_quote(quote))
    return quotes

async def scrape_quotes(base_url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    all_quotes = []
    for _ in range(max_pages):
        html = await fetch_page(base_url)
        quotes = extract_quotes(html)
        if not quotes:
            break
        all_quotes.extend(quotes)
        await asyncio.sleep(1)
    return all_quotes

def save_to_json(data: List[Dict[str, Any]], filename: str = "quotes.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    base_url = "https://quotes.toscrape.com/random"
    quotes = await scrape_quotes(base_url)
    save_to_json(quotes)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
