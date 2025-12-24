import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def fetch_page(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=10000)
        content = await page.content()
        await browser.close()
        return content

def parse_quote(quote: BeautifulSoup) -> Dict[str, Any]:
    fields = {
        "text": {
            "selector": "span.text[itemprop=\"text\"]",
            "attribute": None,
            "type": "string"
        },
        "author": {
            "selector": "small.author[itemprop=\"author\"]",
            "attribute": None,
            "type": "string"
        },
        "author_url": {
            "selector": "a[href^=\"/author/\"]",
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
        },
        "keywords": {
            "selector": "meta.keywords[itemprop=\"keywords\"]",
            "attribute": "content",
            "type": "string"
        }
    }

    result = {}
    for field_name, field_config in fields.items():
        element = quote.select_one(field_config["selector"])
        if not element:
            result[field_name] = None
            continue

        if field_config["attribute"]:
            value = element.get(field_config["attribute"])
        else:
            value = element.get_text(strip=True)

        if field_config["type"] == "url":
            value = f"https://quotes.toscrape.com{value}" if value else None
        elif field_config["type"] == "string":
            value = value if value else None

        result[field_name] = value

    return result

def extract_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    quotes = soup.select("div.quote[itemscope][itemtype=\"http://schema.org/CreativeWork\"]")
    return [parse_quote(quote) for quote in quotes]

async def scrape_quotes(base_url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    all_quotes = []
    for _ in range(max_pages):
        html = await fetch_page(base_url)
        if not html:
            break
        quotes = extract_quotes(html)
        all_quotes.extend(quotes)
        await asyncio.sleep(1)
    return all_quotes

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    base_url = "https://quotes.toscrape.com/random"
    quotes = await scrape_quotes(base_url)
    save_to_json(quotes, "quotes.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
