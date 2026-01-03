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
        await page.wait_for_selector("div.ky-product", state="attached")
        content = await page.content()
        await browser.close()
        return content

def parse_product(product: BeautifulSoup) -> Dict[str, Any]:
    def safe_extract(selector: str, attribute: Optional[str] = None) -> Optional[str]:
        element = product.select_one(selector)
        if not element:
            return None
        if attribute:
            return element.get(attribute)
        return element.get_text(strip=True)

    def parse_rating(rating_text: Optional[str]) -> Optional[float]:
        if not rating_text:
            return None
        try:
            return float(rating_text.split()[0].replace(",", "."))
        except (ValueError, AttributeError):
            return None

    def parse_date(date_text: Optional[str]) -> Optional[str]:
        if not date_text:
            return None
        return date_text.strip()

    return {
        "product_id": safe_extract("div.ky-product"),
        "title": safe_extract("span.ky-product-title"),
        "price": safe_extract("span.ky-product-price.ky-product-sell-price"),
        "image_url": safe_extract("a.ky-product-cover img", "src"),
        "product_url": safe_extract("a.ky-product-cover", "href"),
        "publisher": safe_extract("span.ky-product-publisher a"),
        "author": safe_extract("span.ky-product-author a"),
        "rating": parse_rating(safe_extract("div.ky-product-rating")),
        "publication_date": parse_date(safe_extract("p.ky-product-detail-info span:last-child"))
    }

def scrape_products(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    products = soup.select("div.ky-product")
    return [parse_product(BeautifulSoup(str(p), "html.parser")) for p in products]

async def scrape_all_pages(base_url: str) -> List[Dict[str, Any]]:
    all_products = []
    page_number = 1
    while True:
        url = f"{base_url}&page={page_number}"
        html = await fetch_page(url)
        products = scrape_products(html)
        if not products:
            break
        all_products.extend(products)
        page_number += 1
        await asyncio.sleep(1)
    return all_products

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    base_url = "https://www.kitapyurdu.com/index.php?route=product%2Fbest_sellers&list_id=729&filter_in_shelf=0&filter_in_stock=0"
    products = await scrape_all_pages(base_url)
    save_to_json(products, "products.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
