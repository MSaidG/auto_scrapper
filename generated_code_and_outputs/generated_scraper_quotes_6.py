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
                tags = container.select(self.schema['fields']['tags']['selector'])
                quote['tags'] = [tag.get_text(strip=True) for tag in tags] if tags else []

            if 'tag_urls' in quote and quote['tag_urls'] is not None:
                tag_links = container.select(self.schema['fields']['tag_urls']['selector'])
                tag_urls = []
                for link in tag_links:
                    href = link.get('href', '').strip()
                    if href and not href.startswith('http'):
                        href = urljoin(self.base_url, href)
                    tag_urls.append(href)
                quote['tag_urls'] = tag_urls if tag_urls else []

            quotes.append(quote)

        return quotes

    async def scrape_page(self, page_num: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/page/{page_num}/" if page_num > 1 else self.base_url
        html = await self.fetch_page(url)
        if not html:
            return []
        return self.parse_quotes(html)

    async def scrape_all_pages(self, max_pages: int = 10) -> List[Dict[str, Any]]:
        all_quotes = []
        page_num = 1

        while page_num <= max_pages:
            quotes = await self.scrape_page(page_num)
            if not quotes:
                break
            all_quotes.extend(quotes)
            page_num += 1

        return all_quotes

async def main():
    schema = {
        "entity": "quote",
        "container_selector": "div.quote",
        "fields":{
            "text": {
                "selector": "span.text",
                "attribute": null,
                "type": "string"
            },
            "author": {
                "selector": "small.author",
                "attribute": null,
                "type": "string"
            },
            "author_url": {
                "selector": "a[href^='/author/']",
                "attribute": "href",
                "type": "url"
            },
            "tags": {
                "selector": "a.tag",
                "attribute": null,
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
    quotes = await scraper.scrape_all_pages(max_pages=5)

    # Save results to JSON file
    with open('quotes.json', 'w', encoding='utf-8') as f:
        json.dump(quotes, f, ensure_ascii=False, indent=2)

    print(f"Scraped {len(quotes)} quotes successfully!")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===