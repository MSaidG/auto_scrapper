import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://books.toscrape.com/"

async def fetch_page(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("article.product_pod", timeout=5000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def parse_product(product_soup: BeautifulSoup) -> Dict[str, Any]:
    fields = {
        "name": {
            "selector": "h3 a",
            "attribute": None,
            "type": "string"
        },
        "url": {
            "selector": "h3 a",
            "attribute": "href",
            "type": "url"
        },
        "image_url": {
            "selector": "div.image_container a img",
            "attribute": "src",
            "type": "url"
        },
        "price": {
            "selector": "p.price_color",
            "attribute": None,
            "type": "string"
        },
        "rating": {
            "selector": "p.star-rating",
            "attribute": "class",
            "type": "string"
        },
        "availability": {
            "selector": "p.instock",
            "attribute": None,
            "type": "string"
        }
    }

    product_data = {}
    for field_name, field_config in fields.items():
        selector = field_config["selector"]
        attribute = field_config["attribute"]
        element = product_soup.select_one(selector)

        if element is None:
            product_data[field_name] = None
            continue

        if attribute:
            value = element.get(attribute)
        else:
            value = element.get_text(strip=True)

        if field_config["type"] == "url":
            value = urljoin(BASE_URL, value) if value else None

        product_data[field_name] = value

    return product_data

async def scrape_page(url: str) -> List[Dict[str, Any]]:
    html = await fetch_page(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    products = soup.select("article.product_pod")
    return [parse_product(product) for product in products]

async def scrape_all_pages() -> List[Dict[str, Any]]:
    all_products = []
    page_number = 1
    while True:
        url = f"{BASE_URL}catalogue/page-{page_number}.html"
        products = await scrape_page(url)
        if not products:
            break
        all_products.extend(products)
        page_number += 1
        await asyncio.sleep(1)
    return all_products

def save_to_json(data: List[Dict[str, Any]], filename: str = "products.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    products = await scrape_all_pages()
    save_to_json(products)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
