import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

class QuoteScraper:
    def __init__(self, base_url: str, schema: Dict[str, Any]):
        self.base_url = base_url
        self.schema = schema
        self.rate_limit = 1.0  # seconds

    async def fetch_page(self, page_url: str) -> Optional[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()
            try:
                await page.goto(page_url, timeout=30000)
                await asyncio.sleep(self.rate_limit)
                content = await page.content()
                return content
            except Exception as e:
                print(f"Error fetching {page_url}: {e}")
                return None
            finally:
                await browser.close()

    def extract_field(self, element, field_config: Dict[str, Any]) -> Any:
        selector = field_config["selector"]
        attribute = field_config["attribute"]
        field_type = field_config["type"]

        if field_type == "string":
            if attribute:
                return element.select_one(selector).get(attribute, "").strip() if element.select_one(selector) else None
            else:
                return element.select_one(selector).get_text(strip=True) if element.select_one(selector) else None
        elif field_type == "url":
            if attribute:
                href = element.select_one(selector).get(attribute, "").strip() if element.select_one(selector) else None
                return urljoin(self.base_url, href) if href else None
            else:
                return None
        return None

    def parse_quotes(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        containers = soup.select(self.schema["container_selector"])
        quotes = []

        for container in containers:
            quote = {}
            for field_name, field_config in self.schema["fields"].items():
                value = self.extract_field(container, field_config)
                if field_name in ["tags", "tag_urls"] and value:
                    value = [v.strip() for v in value] if isinstance(value, list) else [value]
                quote[field_name] = value
            quotes.append(quote)

        return quotes

    async def scrape_page(self, page_url: str) -> List[Dict[str, Any]]:
        html = await self.fetch_page(page_url)
        if not html:
            return []
        return self.parse_quotes(html)

    async def scrape_all_pages(self, max_pages: int = 10) -> List[Dict[str, Any]]:
        all_quotes = []
        current_page = 1
        base_url = self.base_url

        while current_page <= max_pages:
            page_url = f"{base_url}/page/{current_page}/" if current_page > 1 else base_url
            quotes = await self.scrape_page(page_url)
            if not quotes:
                break
            all_quotes.extend(quotes)
            current_page += 1

        return all_quotes

async def main():
    schema = {
        "entity": "quote",
        "container_selector": "div.quote",
        "fields": {
            "text": {
                "selector": "span.text",
                "attribute": None,
                "type": "string"
            },
            "author": {
                "selector": "small.author",
                "attribute": None,
                "type": "string"
            },
            "author_url": {
                "selector": "a[href^='/author/']",
                "attribute": "href",
                "type": "url"
            },
            "tags": {
                "selector": "div.tags a.tag",
                "attribute": None,
                "type": "string"
            },
            "tag_urls": {
                "selector": "div.tags a.tag",
                "attribute": "href",
                "type": "url"
            }
        }
    }

    scraper = QuoteScraper("http://quotes.toscrape.com", schema)
    quotes = await scraper.scrape_all_pages(max_pages=5)

    with open("quotes.json", "w") as f:
        json.dump(quotes, f, indent=2)

    print(f"Scraped {len(quotes)} quotes")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
