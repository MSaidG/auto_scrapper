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
            await page.goto(url, timeout=30000)
            await page.wait_for_selector("article.product_pod", timeout=10000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def parse_product(container: BeautifulSoup) -> Dict[str, Any]:
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

    product = {}
    for field_name, config in fields.items():
        selector = config["selector"]
        attribute = config["attribute"]
        element = container.select_one(selector)
        if element:
            if attribute:
                value = element.get(attribute, None)
            else:
                value = element.get_text(strip=True)
            if value:
                if config["type"] == "url":
                    value = urljoin(BASE_URL, value)
                product[field_name] = value
            else:
                product[field_name] = None
        else:
            product[field_name] = None
    return product

async def scrape_page(url: str) -> List[Dict[str, Any]]:
    html = await fetch_page(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select("article.product_pod")
    products = [parse_product(container) for container in containers]
    return products

async def scrape_all_pages() -> List[Dict[str, Any]]:
    all_products = []
    current_url = BASE_URL
    while current_url:
        products = await scrape_page(current_url)
        if not products:
            break
        all_products.extend(products)
        soup = BeautifulSoup(await fetch_page(current_url), "html.parser")
        next_button = soup.select_one("li.next a")
        if next_button and "href" in next_button.attrs:
            current_url = urljoin(BASE_URL, next_button["href"])
        else:
            current_url = None
        await asyncio.sleep(1)
    return all_products

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    products = await scrape_all_pages()
    save_to_json(products, "products.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
