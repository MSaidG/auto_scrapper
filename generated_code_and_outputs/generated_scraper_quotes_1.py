import json
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin
from typing import Union
from bs4 import BeautifulSoup, Tag
from playwright.sync_api import sync_playwright

class QuoteScraper:
    def __init__(self, base_url: str, schema: Dict[str, Any]):
        self.base_url = base_url
        self.schema = schema
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.browser.close()
        self.playwright.stop()
        
    def safe_urljoin(self, base: str, href: Union[str, None, list]) -> str | None:
        href_str = self.safe_value(href)
        if href_str is None:
            return None
        return urljoin(base, href_str)

    def safe_value(self, value: Union[str, None, list]) -> str | None:
        """Convert BeautifulSoup attribute value to str or None safely"""
        if isinstance(value, list):
            value = value[0] if value else None
        if value is None:
            return None
        return str(value)

    def fetch_page(self, url: str) -> str:
        """Fetch page content with rate limiting"""
        time.sleep(1)  # Rate limit: 1 request per second
        with self.browser.new_page() as page:
            page.goto(url)
            return page.content()

    def extract_field(self, element: Tag, field_config: Dict[str, Any]) -> Optional[str]:
        """Extract a single field from an element based on schema"""
        selector = field_config["selector"]
        attribute = field_config["attribute"]
        field_type = field_config["type"]

        try:
            if selector:
                target = element.select_one(selector)
                if not target:
                    return None

                if attribute:
                    raw_value = target.get(attribute, None)
                else:
                    raw_value = target.get_text(strip=True)

                value = self.safe_value(raw_value)

                if value:
                    if field_type == "url":
                        value = self.safe_urljoin(self.base_url, value)
                    return value
        except Exception:
            return None

        return None

    def extract_quote(self, quote_element: Tag) -> Dict[str, Any]:
        """Extract a single quote according to schema"""
        quote_data = {}
        fields = self.schema["fields"]

        for field_name, field_config in fields.items():
            if field_name in ["tags", "tag_urls"]:
                # Handle multiple tags
                tags = []
                for tag_element in quote_element.select(field_config["selector"]):
                    if field_config["attribute"]:
                        value = tag_element.get(field_config["attribute"], "")
                    else:
                        value = tag_element.get_text(strip=True)

                    if value:
                        if field_config["type"] == "url":
                            value = self.safe_urljoin(self.base_url, value)
                        tags.append(value)
                quote_data[field_name] = tags if tags else None
            else:
                # Handle single fields
                value = self.extract_field(quote_element, field_config)
                quote_data[field_name] = value

        return quote_data

    def scrape_page(self, url: str) -> List[Dict[str, Any]]:
        """Scrape a single page of quotes"""
        html = self.fetch_page(url)
        soup = BeautifulSoup(html, 'html.parser')
        container_selector = self.schema["container_selector"]

        quotes = []
        for quote_element in soup.select(container_selector):
            if isinstance(quote_element, Tag):
                quote_data = self.extract_quote(quote_element)
                quotes.append(quote_data)

        return quotes

    def scrape_all_pages(self, start_url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
        all_quotes = []
        current_url = start_url

        for _ in range(max_pages):
            page_quotes = self.scrape_page(current_url)
            if not page_quotes:
                break

            all_quotes.extend(page_quotes)

            # Handle pagination if applicable
            soup = BeautifulSoup(self.fetch_page(current_url), 'html.parser')
            next_page = soup.select_one('li.next a')
            if next_page and next_page.get('href'):
                current_url = urljoin(self.base_url, next_page['href'])
            else:
                break

        return all_quotes  # ✅ Make sure we always return



schema = {'entity': 'quote', 'container_selector': 'div.quote', 'fields': {'text': {'selector': 'span.text', 'attribute': None, 'type': 'string'}, 'author': {'selector': 'small.author', 'attribute': None, 'type': 'string'}, 'author_url': {'selector': "a[href^='/author/']", 'attribute': 'href', 'type': 'url'}, 'tags': {'selector': 'a.tag', 'attribute': None, 'type': 'string'}, 'tag_urls': {'selector': 'a.tag', 'attribute': 'href', 'type': 'url'}}}

with QuoteScraper("https://quotes.toscrape.com/", schema) as scraper:
    data = scraper.scrape_all_pages("https://quotes.toscrape.com/")
    print(data[:2])
    with open("ai_generated_code_output.json", "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print("Saved extracted data to ai_generated_code_output.json")
