import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://quotes.toscrape.com/random"

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=10000)
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
        "tag_url": {
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

        if field_name == "tags":
            elements = quote_soup.select(selector)
            values = [element.get_text(strip=True) for element in elements]
            quote_data[field_name] = values if values else None
        elif field_name == "tag_url":
            elements = quote_soup.select(selector)
            values = [urljoin(BASE_URL, element.get(attribute, "")) for element in elements]
            quote_data[field_name] = values if values else None
        else:
            element = quote_soup.select_one(selector)
            if element:
                if attribute:
                    value = element.get(attribute)
                    if field_type == "url":
                        value = urljoin(BASE_URL, value) if value else None
                else:
                    value = element.get_text(strip=True)
                    if field_type == "string":
                        value = value if value else None
                quote_data[field_name] = value
            else:
                quote_data[field_name] = None
    return quote_data

async def scrape_quotes(num_quotes: int = 10) -> List[Dict[str, Any]]:
    quotes = []
    for _ in range(num_quotes):
        html = await fetch_page(BASE_URL)
        soup = BeautifulSoup(html, "html.parser")
        quote_containers = soup.select("div.quote")
        for container in quote_containers:
            quote_data = parse_quote(container)
            quotes.append(quote_data)
        await asyncio.sleep(1)
    return quotes

def save_to_json(data: List[Dict[str, Any]], filename: str = "quotes.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main(num_quotes: int = 10) -> None:
    quotes = await scrape_quotes(num_quotes)
    save_to_json(quotes)
    print(f"Scraped {len(quotes)} quotes and saved to quotes.json")

if __name__ == "__main__":
    asyncio.run(main())

# === END OF FILE ===
