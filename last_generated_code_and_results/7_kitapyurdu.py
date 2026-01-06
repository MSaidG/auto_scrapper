import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.kitapyurdu.com/index.php?route=product%2Fbest_sellers&list_id=729&filter_in_shelf=0&filter_in_stock=0"

async def fetch_page(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("div.ky-product", timeout=10000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def extract_field(element, selector: str, attribute: Optional[str]) -> Optional[str]:
    if not element:
        return None
    target = element.select_one(selector)
    if not target:
        return None
    if attribute:
        return target.get(attribute, None)
    return target.get_text(strip=True) if target else None

def parse_product(product_element) -> Dict[str, Any]:
    product = {
        "product_id": None,
        "product_url": None,
        "product_image_url": None,
        "product_title": None,
        "product_price": None,
        "product_publisher": None,
        "product_author": None,
        "product_rating": None,
        "product_publication_date": None
    }

    product_id = extract_field(product_element, "div.ky-product", None)
    if product_id:
        product["product_id"] = product_id

    product_url = extract_field(product_element, "a.ky-product-cover", "href")
    if product_url:
        product["product_url"] = product_url

    product_image_url = extract_field(product_element, "a.ky-product-cover img", "src")
    if product_image_url:
        product["product_image_url"] = product_image_url

    product_title = extract_field(product_element, "span.ky-product-title", None)
    if product_title:
        product["product_title"] = product_title

    product_price = extract_field(product_element, "span.ky-product-price.ky-product-sell-price", None)
    if product_price:
        product["product_price"] = product_price

    product_publisher = extract_field(product_element, "span.ky-product-publisher a", None)
    if product_publisher:
        product["product_publisher"] = product_publisher

    product_author = extract_field(product_element, "span.ky-product-author a", None)
    if product_author:
        product["product_author"] = product_author

    product_rating = extract_field(product_element, "div.ky-product-rating", None)
    if product_rating:
        try:
            product["product_rating"] = float(product_rating)
        except ValueError:
            product["product_rating"] = None

    product_publication_date = extract_field(product_element, "div.ky-product-details p.ky-product-detail-info span:last-child", None)
    if product_publication_date:
        product["product_publication_date"] = product_publication_date

    return product

async def scrape_page(url: str) -> List[Dict[str, Any]]:
    html = await fetch_page(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for product_element in soup.select("div.ky-product"):
        product = parse_product(product_element)
        products.append(product)
    return products

async def scrape_all_pages() -> List[Dict[str, Any]]:
    all_products =all_products = []
    page_number = 1
    while True:
        url = f"{BASE_URL}&page={page_number}"
        products = await scrape_page(url)
        if not products:
            break
        all_products.extend(products)
        page_number += 1
    return all_products

async def main():
    products = await scrape_all_pages()
    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
