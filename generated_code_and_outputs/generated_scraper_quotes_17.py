import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://quotes.toscrape.com/"

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        content = await page.content()
        await browser.close()
        return content

def parse_quote(quote_soup: BeautifulSoup) -> Dict[str, Any]:
    text_elem = quote_soup.select_one("span.text")
    text = text_elem.get_text(strip=True) if text_elem else None

    author_elem = quote_soup.select_one("small.author")
    author = author_elem.get_text(strip=True) if author_elem else None

    author_url_elem = quote_soup.select_one("a[href^='/author/']")
    author_url = urljoin(BASE_URL, author_url_elem["href"]) if author_url_elem else None

    tags_elem = quote_soup.select_one("meta.keywords")
    tags = tags_elem["content"] if tags_elem else None

    tag_links = []
    for tag_elem in quote_soup.select("a.tag"):
        href = tag_elem["href"]
        tag_links.append(urljoin(BASE_URL, href))

    return {
        "text": text,
        "author": author,
        "author_url": author_url,
        "tags": tags,
        "tag_links": tag_links
    }

def extract_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    quote_containers = soup.select("div.quote")
    quotes = []
    for container in quote_containers:
        quote = parse_quote(container)
        quotes.append(quote)
    return quotes

async def scrape_page(url: str) -> List[Dict[str, Any]]:
    html = await fetch_page(url)
    return extract_quotes(html)

async def scrape_all_pages() -> List[Dict[str, Any]]:
    all_quotes = []
    page_url = BASE_URL
    while page_url:
        quotes = await scrape_page(page_url)
        all_quotes.extend(quotes)
        next_page_elem = BeautifulSoup(await fetch_page(page_url), "html.parser").select_one("li.next > a")
        page_url = urljoin(BASE_URL, next_page_elem["href"]) if next_page_elem else None
        await asyncio.sleep(1)
    return all_quotes

def save_to_json(data: List[Dict[str, Any]], filename: str = "quotes.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    quotes = await scrape_all_pages()
    save_to_json(quotes)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
