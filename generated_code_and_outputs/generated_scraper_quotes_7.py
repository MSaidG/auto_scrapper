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

    async def fetch_page(self, url: str) -> Optional[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=30000)
                await asyncio.sleep(self.rate_limit)
                content = await page.content()
                return content
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                return None
            finally:
                await browser.close()

    def extract_field(self, element, field_config: Dict[str, Any]) -> Any:
        selector = field_config["selector"]
        attribute = field_config["attribute"]
        field_type = field_config["type"]

        if not element:
            return None

        if field_type == "string":
            if attribute:
                return element.get(attribute, None)
            else:
                return element.get_text(strip=True) if element else None
        elif field_type == "url":
            if attribute:
                href = element.get(attribute, None)
                return urljoin(self.base_url, href) if href else None
            return None
        return None

    def parse_quote(self, quote_element) -> Dict[str, Any]:
        quote_data = {}
        fields = self.schema["fields"]

        for field_name, field_config in fields.items():
            selector = field_config["selector"]
            elements = quote_element.select(selector)

            if field_name in ["tags", "tag_urls"]:
                values = []
                for elem in elements:
                    value = self.extract_field(elem, field_config)
                    if value:
                        values.append(value)
                quote_data[field_name] = values if values else None
            else:
                elem = elements[0] if elements else None
                quote_data[field_name] = self.extract_field(elem, field_config)

        return quote_data

    def parse_page(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        container_selector = self.schema["container_selector"]
        quote_elements = soup.select(container_selector)

        quotes = []
        for quote_element in quote_elements:
            quote_data = self.parse_quote(quote_element)
            quotes.append(quote_data)

        return quotes

    async def scrape(self, max_pages: int = 10) -> List[Dict[str, Any]]:
        all_quotes = []
        current_page = 1

        while current_page <= max_pages:
            if current_page == 1:
                url = self.base_url
            else:
                url = f"{self.base_url}/page/{current_page}/"

            html = await self.fetch_page(url)
            if not html:
                break

            quotes = self.parse_page(html)
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
                "selector": "a.tag",
                "attribute": None,
                "type": "string"
            },
            "tag_urls": {
                "selector": "a.tag",
                "attribute": "href",
                "type": "url"
            }
        }
    }

    base_url = "http://quotes.toscrape.com"
    scraper = QuoteScraper(base_url, schema)
    quotes = await scraper.scrape(max_pages=5)

    print(f"Scraped {len(quotes)} quotes")
    for quote in quotes[:3]:  # Print first 3 quotes as sample
        print(json.dumps(quote, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===