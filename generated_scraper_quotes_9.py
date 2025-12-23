import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

class QuoteScraper:
    def __init__(self, base_url: str, schema: Dict[str, Any]):
        self.base_url = base_url
        self.schema = schema
        self.quotes: List[Dict[str, Any]] = []

    async def fetch_page(self, page_number: int) -> Optional[str]:
        url = f"{self.base_url}?page={page_number}"
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()
            try:
                await page.goto(url, timeout=10000)
                await asyncio.sleep(1)  # Rate limit: 1 request per second
                content = await page.content()
                return content
            except Exception as e:
                print(f"Error fetching page {page_number}: {e}")
                return None
            finally:
                await browser.close()

    def extract_quotes(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        containers = soup.select(self.schema["container_selector"])
        quotes = []
        for container in containers:
            quote = {}
            for field_name, field_config in self.schema["fields"].items():
                elements = container.select(field_config["selector"])
                if field_name == "tags":
                    quote[field_name] = [tag.get_text(strip=True) for tag in elements]
                else:
                    quote[field_name] = elements[0].get_text(strip=True) if elements else None
            quotes.append(quote)
        return quotes

    async def scrape(self, max_pages: int = 10) -> None:
        page_number = 1
        while page_number <= max_pages:
            html = await self.fetch_page(page_number)
            if not html:
                break
            quotes = self.extract_quotes(html)
            if not quotes:
                break
            self.quotes.extend(quotes)
            page_number += 1

    def save_to_json(self, filename: str) -> None:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.quotes, f, ensure_ascii=False, indent=2)

async def main():
    schema = {
        "entity": "quote",
        "container_selector": ".quote",
        "fields": {
            "text": {
                "selector": ".text",
                "attribute": None,
                "type": "string"
            },
            "author": {
                "selector": ".author",
                "attribute": None,
                "type": "string"
            },
            "tags": {
                "selector": ".tag",
                "attribute": None,
                "type": "string"
            }
        }
    }
    base_url = "https://quotes.toscrape.com/scroll"
    scraper = QuoteScraper(base_url, schema)
    await scraper.scrape(max_pages=10)
    scraper.save_to_json("quotes.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===