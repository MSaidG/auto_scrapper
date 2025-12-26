import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("div.quote", state="attached")
        content = await page.content()
        await browser.close()
        return content

async def scroll_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("div.quote", state="attached")
        last_height = await page.evaluate("document.body.scrollHeight")
        while True:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        content = await page.content()
        await browser.close()
        return content

def parse_quotes(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    quotes = []
    for container in soup.select("div.quote"):
        quote = {
            "text": None,
            "author": None,
            "tags": []
        }
        text_span = container.select_one("span.text")
        if text_span:
            quote["text"] = text_span.get_text(strip=True)
        author_small = container.select_one("small.author")
        if author_small:
            quote["author"] = author_small.get_text(strip=True)
        tags = container.select("div.tags a.tag")
        if tags:
            quote["tags"] = [tag.get_text(strip=True) for tag in tags]
        quotes.append(quote)
    return quotes

async def scrape_quotes(base_url: str) -> List[Dict[str, Any]]:
    html = await scroll_page(base_url)
    return parse_quotes(html)

async def main():
    base_url = "https://quotes.toscrape.com/scroll"
    quotes = await scrape_quotes(base_url)
    with open("quotes.json", "w", encoding="utf-8") as f:
        json.dump(quotes, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
