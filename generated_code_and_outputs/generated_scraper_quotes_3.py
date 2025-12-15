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
                    if field_config['attribute']:
                        value = elements[0].get(field_config['attribute'], '')
                        if value is not None:
                            value = str(value).strip()
                    else:
                        value = elements[0].get_text(strip=True)
                    quote[field_name] = value if value else None
                elif field_config['type'] == 'url':
                    if field_config['attribute']:
                        value = elements[0].get(field_config['attribute'], '')
                        if value is not None:
                            value = str(value).strip()
                        if value:
                            value = urljoin(self.base_url, value)
                    else:
                        value = None
                    quote[field_name] = value if value else None
                elif field_config['type'] == 'list':
                    values = []
                    for element in elements:
                        if field_config['attribute']:
                            val = element.get(field_config['attribute'], '')
                            if val is not None:
                                val = str(val).strip()
                        else:
                            val = element.get_text(strip=True)
                        if val:
                            values.append(val)
                    quote[field_name] = values if values else None

            # Handle tags and tag_urls as lists
            if 'tags' in quote and quote['tags'] is not None:
                quote['tags'] = [tag.strip() for tag in quote['tags']]
            if 'tag_urls' in quote and quote['tag_urls'] is not None:
                quote['tag_urls'] = [urljoin(self.base_url, url.strip()) for url in quote['tag_urls']]

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
    # Example schema for quotes.toscrape.com
    schema = {
        "entity": "quote",
        "container_selector": "div.quote",
        "fields": {
            "text": {"selector": "span.text", "attribute": None, "type": "string"},
            "author": {"selector": "small.author", "attribute": None, "type": "string"},
            "author_url": {"selector": "a[href^='/author/']", "attribute": "href", "type": "url"},
            "tags": {"selector": "a.tag", "attribute": None, "type": "list"},
            "tag_urls": {"selector": "a.tag", "attribute": "href", "type": "list"}
        }
    }

    scraper = QuoteScraper(base_url="https://quotes.toscrape.com", schema=schema)
    data = await scraper.scrape_all_pages(max_pages=5)  # adjust max_pages as needed

    # Save to JSON
    with open("generated_scraper_quotes_3_output.json", "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Scraped {len(data)} quotes. Saved to generated_scraper_quotes_3_output.json")

if __name__ == "__main__":
    asyncio.run(main())
