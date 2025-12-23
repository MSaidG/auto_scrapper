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
        url = f"{self.base_url}/page/{page_number}/"
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(url, timeout=10000)
                content = await page.content()
                await browser.close()
                return content
        except Exception as e:
            print(f"Error fetching page {page_number}: {e}")
            return None

    def parse_quote(self, quote_element) -> Dict[str, Any]:
        quote_data = {}
        fields = self.schema.get("fields", {})

        for field_name, field_config in fields.items():
            selector = field_config.get("selector")
            attribute = field_config.get("attribute")
            field_type = field_config.get("type")

            elements = quote_element.select(selector)
            if not elements:
                quote_data[field_name] = None
                continue

            if field_type == "string":
                value = elements[0].get_text(strip=True) if elements else None
            elif field_type == "url":
                value = elements[0].get(attribute, None) if elements else None
                if value and not value.startswith("http"):
                    value = f"{self.base_url}{value}"
            else:
                value = None

            if field_name in ["tags", "tag_urls"]:
                value = [elem.get_text(strip=True) if field_type == "string" else
                        (f"{self.base_url}{elem.get(attribute, '')}" if field_type == "url" else None)
                        for elem in elements]

            quote_data[field_name] = value if value else None

        return quote_data

    def extract_quotes(self, html_content: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html_content, "html.parser")
        container_selector = self.schema.get("container_selector", "")
        quote_elements = soup.select(container_selector)

        quotes = []
        for quote_element in quote_elements:
            quote_data = self.parse_quote(quote_element)
            quotes.append(quote_data)

        return quotes

    async def scrape_pages(self, max_pages: int = 10) -> None:
        for page_number in range(1, max_pages + 1):
            print(f"Scraping page {page_number}...")
            html_content = await self.fetch_page(page_number)
            if not html_content:
                print(f"Failed to fetch page {page_number}, skipping...")
                continue

            page_quotes = self.extract_quotes(html_content)
            if not page_quotes:
                print(f"No quotes found on page {page_number}, stopping...")
                break

            self.quotes.extend(page_quotes)
            await asyncio.sleep(1)  # Rate limiting

    def save_to_json(self, filename: str) -> None:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.quotes, f, ensure_ascii=False, indent=2)

async def main():
    base_url = "http://quotes.toscrape.com"
    schema = {
        "entity": "quote",
        "container_selector": "div.quote",
        "fields": {
            "text":{
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

    scraper = QuoteScraper(base_url, schema)
    await scraper.scrape_pages(max_pages=5)
    scraper.save_to_json("quotes.json")
    print(f"Scraped {len(scraper.quotes)} quotes successfully!")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===