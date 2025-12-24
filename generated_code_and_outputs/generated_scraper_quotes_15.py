import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://quotes.toscrape.com/random"
OUTPUT_FILE = "quotes.json"

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        content = await page.content()
        await browser.close()
        return content

def parse_quote(quote_soup: BeautifulSoup) -> Dict[str, Any]:
    fields = {
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

    quote_data = {}
    for field_name, field_config in fields.items():
        selector = field_config["selector"]
        attribute = field_config["attribute"]
        field_type = field_config["type"]

        elements = quote_soup.select(selector)
        if not elements:
            quote_data[field_name] = None
            continue

        if field_type == "string":
            if attribute:
                value = elements[0].get(attribute, None)
            else:
                value = elements[0].get_text(strip=True) if elements else None
        elif field_type == "url":
            if attribute:
                value = elements[0].get(attribute, None)
                if value:
                    value = urljoin(BASE_URL, value)
            else:
                value = None
        else:
            value = None

        if field_name in ["tags", "tag_urls"]:
            if attribute:
                values = [urljoin(BASE_URL, elem.get(attribute, "")) for elem in elements]
            else:
                values = [elem.get_text(strip=True) for elem in elements]
            quote_data[field_name] = values if values else None
        else:
            quote_data[field_name] = value

    return quote_data

async def scrape_quotes(num_requests: int = 10) -> List[Dict[str, Any]]:
    quotes = []
    for _ in range(num_requests):
        html = await fetch_page(BASE_URL)
        soup = BeautifulSoup(html, "html.parser")
        quote_containers = soup.select("div.quote")
        for container in quote_containers:
            quote_data = parse_quote(container)
            quotes.append(quote_data)
        await asyncio.sleep(1)
    return quotes

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    quotes = await scrape_quotes()
    save_to_json(quotes, OUTPUT_FILE)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
