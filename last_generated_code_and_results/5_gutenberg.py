import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def fetch_page(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        content = await page.content()
        await browser.close()
        return content

def parse_book(book_element) -> Dict[str, Any]:
    book = {
        "book_url": None,
        "cover_image_url": None,
        "title": None,
        "author": None,
        "download_count": None
    }

    link = book_element.select_one("a.link")
    if link and link.has_attr("href"):
        book["book_url"] = link["href"]

    cover = book_element.select_one("img.cover-thumb")
    if cover and cover.has_attr("src"):
        book["cover_image_url"] = cover["src"]

    title = book_element.select_one("span.title")
    if title:
        book["title"] = title.get_text(strip=True)

    author = book_element.select_one("span.subtitle")
    if author:
        book["author"] = author.get_text(strip=True)

    download = book_element.select_one("span.extra")
    if download:
        text = download.get_text(strip=True)
        try:
            book["download_count"] = int(text.replace(",", ""))
        except ValueError:
            pass

    return book

def extract_books(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for book_element in soup.select("li.booklink"):
        book = parse_book(book_element)
        books.append(book)
    return books

async def scrape_page(page_num: int) -> List[Dict[str, Any]]:
    url = f"https://www.gutenberg.org/ebooks/search/?start_index={page_num * 25}"
    html = await fetch_page(url)
    return extract_books(html)

async def scrape_all_pages(max_pages: int = 10) -> List[Dict[str, Any]]:
    all_books = []
    for page in range(max_pages):
        books = await scrape_page(page)
        if not books:
            break
        all_books.extend(books)
        await asyncio.sleep(1)
    return all_books

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def main():
    books = await scrape_all_pages()
    save_to_json(books, "books.json")

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
