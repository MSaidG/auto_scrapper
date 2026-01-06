import asyncio
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

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
        "title": {
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
            "attribute": None,
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
        if element:
            if attribute:
                value = element.get(attribute)
            else:
                value = element.get_text(strip=True)
            if field_config["type"] == "url":
                value = urljoin(BASE_URL, value)
            product_data[field_name] = value
        else:
            product_data[field_name] = None
    return product_data

def parse_page(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for product_soup in soup.select("article.product_pod"):
        product_data = parse_product(product_soup)
        products.append(product_data)
    return products

async def scrape_all_pages() -> List[Dict[str, Any]]:
    all_products = []
    page_number = 1
    while True:
        url = f"{BASE_URL}catalogue/page-{page_number}.html"
        html = await fetch_page(url)
        if not html:
            break
        products = parse_page(html)
        if not products:
            break
        all_products.extend(products)
        page_number += 1
        await asyncio.sleep(1)
    return all_products

async def main():
    products = await scrape_all_pages()
    with open("scraped_products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
