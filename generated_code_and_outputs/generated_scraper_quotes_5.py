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

    def parse_quotes(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        containers = soup.select(self.schema['container_selector'])
        quotes = []

        for container in containers:
            quote = {}
            for field_name, field_config in self.schema['fields'].items():
                elements = container.select(field_config['selector'])
                if not elements:
                    quote[field_name] = None
                    continue

                if field_config['type'] == 'string':
                    if field_config['attribute'] is None:
                        value = elements[0].get_text(strip=True)
                    else:
                        value = elements[0].get(field_config['attribute'], '').strip()
                elif field_config['type'] == 'url':
                    value = elements[0].get(field_config['attribute'], '').strip()
                    if value and not value.startswith('http'):
                        value = urljoin(self.base_url, value)
                else:
                    value = None

                quote[field_name] = value if value else None

            # Handle tags and tag_urls as lists
            if 'tags' in quote and quote['tags'] is not None:
                tags = [tag.strip() for tag in container.select(self.schema['fields']['tags']['selector'])]
                quote['tags'] = tags if tags else None

            if 'tag_urls' in quote and quote['tag_urls'] is not None:
                tag_urls = []
                for tag in container.select(self.schema['fields']['tag_urls']['selector']):
                    url = tag.get('href', '').strip()
                    if url and not url.startswith('http'):
                        url = urljoin(self.base_url, url)
                    tag_urls.append(url)
                quote['tag_urls'] = tag_urls if tag_urls else None

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

        while current_page <= max_pages:
            page_url = f"{self.base_url}/page/{current_page}/" if current_page > 1 else self.base_url
            quotes = await self.scrape_page(page_url)

            if not quotes:
                break

            all_quotes.extend(quotes)
            current_page += 1

        return all_quotes

async def main():
    schema = {
        "entity": "quote",
        "container_selector": "div.quote","fields": {
            "text": {
                "selector": "span.text",
                "type": "string",
                "attribute": None
            },
            "author": {
                "selector": "small.author",
                "type": "string",
                "attribute": None
            },
            "tags": {
                "selector": "div.tags a.tag",
                "type": "list",
                "attribute": None
            },
            "tag_urls": {
                "selector": "div.tags a.tag",
                "type": "list",
                "attribute": "href"
            }
        }
    }

    base_url = "http://quotes.toscrape.com"
    scraper = QuoteScraper(base_url, schema)
    quotes = await scraper.scrape_all_pages(max_pages=5)

    # Save results to JSON file
    with open('quotes.json', 'w', encoding='utf-8') as f:
        json.dump(quotes, f, ensure_ascii=False, indent=2)

    print(f"Scraped {len(quotes)} quotes successfully!")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===