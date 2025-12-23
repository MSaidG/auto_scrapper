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
        self.quotes: List[Dict[str, Any]] = []

    async def fetch_page(self, url: str) -> Optional[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=10000)
                await asyncio.sleep(1)  # Rate limit: 1 request per second
                content = await page.content()
                return content
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                return None
            finally:
                await browser.close()

    def extract_quotes(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        containers = soup.select(self.schema["container_selector"])
        quotes = []

        for container in containers:
            quote = {}
            for field_name, field_config in self.schema["fields"].items():
                selector = field_config["selector"]
                attribute = field_config["attribute"]
                field_type = field_config["type"]

                elements = container.select(selector)
                if not elements:
                    quote[field_name] = None
                    continue

                if field_type == "string":
                    value = (
                        elements[0].get_text(strip=True)
                        if not attribute
                        else elements[0].get(attribute, "")
                    )
                    quote[field_name] = value if value else None
                elif field_type == "url":
                    value = elements[0].get(attribute, "")
                    if value and not value.startswith("http"):
                        value = urljoin(self.base_url, value)
                    quote[field_name] = value if value else None
                elif field_type == "list":
                    values = [elem.get_text(strip=True) for elem in elements]
                    quote[field_name] = values if values else None
                else:
                    quote[field_name] = None

            quotes.append(quote)

        return quotes

    async def scrape(self, max_pages: int = 10) -> None:
        for _ in range(max_pages):
            html = await self.fetch_page(self.base_url)
            if not html:
                continue

            quotes = self.extract_quotes(html)
            if not quotes:
                continue

            self.quotes.extend(quotes)

    def save_to_json(self, filename: str) -> None:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.quotes, f, ensure_ascii=False, indent=2)


async def main():
    schema = {
        "entity": "quote",
        "container_selector": "div.quote",
        "fields": {
            "text": {"selector": "span.text", "attribute": None, "type": "string"},
            "author": {"selector": "small.author", "attribute": None, "type": "string"},
            "author_url": {
                "selector": "a[href^='/author/']",
                "attribute": "href",
                "type": "url",
            },
            "tags": {"selector": "a.tag", "attribute": None, "type": "string"},
            "tag_urls": {"selector": "a.tag", "attribute": "href", "type": "url"},
            "keywords": {
                "selector": "meta.keywords",
                "attribute": "content",
                "type": "string",
            },
        },
    }

    scraper = QuoteScraper("http://quotes.toscrape.com", schema)
    await scraper.scrape(max_pages=1)
    scraper.save_to_json("quotes.json")
    print(f"Scraped {len(scraper.quotes)} quotes.")


if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
