# Production-Ready Web Scraper for Quotes

import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

class QuoteScraper:
    def __init__(self, base_url: str, schema: Dict[str, Any], rate_limit: float = 1.0):
        """
        Initialize the scraper with base URL and schema.

        Args:
            base_url: The base URL of the website to scrape
            schema: The data schema defining how to extract data
            rate_limit: Minimum seconds between requests (default: 1.0)
        """
        self.base_url = base_url
        self.schema = schema
        self.rate_limit = rate_limit
        self.last_request_time = 0

    async def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = asyncio.get_event_loop().time() - self.last_request_time
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self.last_request_time = asyncio.get_event_loop().time()

    async def _fetch_page(self, url: str) -> str:
        """Fetch a page using Playwright."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, timeout=60000)
            content = await page.content()
            await browser.close()
            return content

    def _extract_field(self, element, field_config: Dict[str, Any]) -> Optional[Any]:
        """
        Extract a single field from an element based on field configuration.

        Args:
            element: BeautifulSoup element to extract from
            field_config: Configuration for the field

        Returns:
            Extracted value or None if not found
        """
        selector = field_config["selector"]
        attribute = field_config["attribute"]
        field_type = field_config["type"]

        # Find the element
        field_element = element.select_one(selector)
        if not field_element:
            return None

        # Extract value based on attribute or text
        if attribute:
            value = field_element.get(attribute)
        else:
            value = field_element.get_text(strip=True)

        # Process based on type
        if not value:
            return None

        if field_type == "url":
            return urljoin(self.base_url, value)
        elif field_type == "string":
            return value.strip()
        else:
            return value

    def _extract_entity(self, container: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract a single entity from a container element.

        Args:
            container: BeautifulSoup element representing the container

        Returns:
            Dictionary with extracted fields
        """
        entity = {}
        for field_name, field_config in self.schema["fields"].items():
            value = self._extract_field(container, field_config)
            if value is not None:
                entity[field_name] = value
        return entity

    def _parse_page(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse a page and extract all entities.

        Args:
            html: HTML content of the page

        Returns:
            List of extracted entities
        """
        soup = BeautifulSoup(html, 'html.parser')
        containers = soup.select(self.schema["container_selector"])
        return [self._extract_entity(container) for container in containers]

    async def scrape_page(self, url: str) -> List[Dict[str, Any]]:
        """Scrape a single page and return extracted data."""
        await self._enforce_rate_limit()
        html = await self._fetch_page(url)
        return self._parse_page(html)

schema = {'entity': 'quote', 'container_selector': 'div.quote', 'fields': {'text': {'selector': 'span.text', 'attribute': None, 'type': 'string'}, 'author': {'selector': 'small.author', 'attribute': None, 'type': 'string'}, 'author_url': {'selector': "a[href^='/author/']", 'attribute': 'href', 'type': 'url'}, 'tags': {'selector': 'a.tag', 'attribute': None, 'type': 'string'}, 'tag_urls': {'selector': 'a.tag', 'attribute': 'href', 'type': 'url'}}}

scraper = QuoteScraper(base_url="https://quotes.toscrape.com/", schema=schema)
data = asyncio.run(scraper.scrape_page("https://quotes.toscrape.com/"))

with open("generated_scraper_quotes_2_output.json", "w", encoding="utf-8") as f:
    for item in data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print("Saved extracted data to generated_scraper_quotes_2_output.json")
