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
        await page.wait_for_selector("select.form-control[name='author'] option", state="attached")
        content = await page.content()
        await browser.close()
        return content

def parse_author_data(html: str) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html, 'html.parser')
    authors = []
    for option in soup.select("select.form-control[name='author'] option"):
        author_name = option.get_text(strip=True) if option else None
        author_value = option.get('value') if option else None
        authors.append({
            "author_name": author_name,
            "author_value": author_value
        })
    return authors

async def scrape_authors(base_url: str, retries: int = 3) -> List[Dict[str, Optional[str]]]:
    for attempt in range(retries):
        try:
            html = await fetch_page(base_url)
            return parse_author_data(html)
        except Exception as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Failed after {retries} retries: {str(e)}")
            await asyncio.sleep(1)
    return []

def save_to_json(data: List[Dict[str, Optional[str]]], filename: str) -> None:
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    base_url = "https://quotes.toscrape.com/search.aspx"
    authors = await scrape_authors(base_url)
    save_to_json(authors, "authors.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
