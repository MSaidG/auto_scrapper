import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.scrapethissite.com/pages/simple/"

async def fetch_page(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_selector("div.col-md-4.country", timeout=5000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def parse_html(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select("div.col-md-4.country")
    results = []
    for container in containers:
        name = container.select_one("h3.country-name")
        capital = container.select_one("span.country-capital")
        population = container.select_one("span.country-population")
        area = container.select_one("span.country-area")

        result = {
            "name": name.get_text(strip=True) if name else None,
            "capital": capital.get_text(strip=True) if capital else None,
            "population": float(population.get_text(strip=True).replace(",", "")) if population else None,
            "area": float(area.get_text(strip=True).replace(",", "")) if area else None,
        }
        results.append(result)
    return results

async def scrape_data() -> List[Dict[str, Any]]:
    html = await fetch_page(BASE_URL)
    if not html:
        return []
    return parse_html(html)

def save_to_json(data: List[Dict[str, Any]], filename: str = "output.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main() -> None:
    data = await scrape_data()
    save_to_json(data)

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
