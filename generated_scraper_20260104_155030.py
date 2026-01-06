import asyncio
import json
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

async def fetch_page(url: str) -> Optional[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("div.s-post-summary.js-post-summary", timeout=10000)
            content = await page.content()
            return content
        except Exception:
            return None
        finally:
            await browser.close()

def extract_field(soup: BeautifulSoup, selector: str, attribute: Optional[str] = None, field_type: str = "string") -> Any:
    element = soup.select_one(selector)
    if not element:
        return None
    if attribute:
        value = element.get(attribute)
    else:
        value = element.get_text(strip=True)
    if not value:
        return None
    if field_type == "number":
        try:
            return int(value.replace(",", ""))
        except ValueError:
            return None
    elif field_type == "url":
        return value if value.startswith("http") else f"https://stackoverflow.com{value}"
    elif field_type == "date":
        return value
    return value

def parse_question(container: BeautifulSoup) -> Dict[str, Any]:
    question = {}
    question["title"] = extract_field(container, "h3.s-post-summary--content-title a.s-link span[itemprop='name']", None, "string")
    question["url"] = extract_field(container, "h3.s-post-summary--content-title a.s-link", "href", "url")
    question["excerpt"] = extract_field(container, "div.s-post-summary--content-excerpt[itemprop='text']", None, "string")
    question["vote_count"] = extract_field(container, "span.s-post-summary--stats-item-number[itemprop='upvoteCount']", None, "number")
    question["answer_count"] = extract_field(container, "span.s-post-summary--stats-item-number[itemprop='answerCount']", None, "number")
    question["view_count"] = extract_field(container, "div.s-post-summary--stats-item:has(span.s-post-summary--stats-item-unit:contains('views')) span.s-post-summary--stats-item-number", None, "number")
    question["tags"] = [tag.get_text(strip=True) for tag in container.select("div.s-post-summary--meta-tags a.s-tag.post-tag")]
    question["author_name"] = extract_field(container, "div.s-user-card--info a.flex--item span[itemprop='name']", None, "string")
    question["author_url"] = extract_field(container, "div.s-user-card--info a.flex--item", "href", "url")
    question["author_reputation"] = extract_field(container, "div.s-user-card--info li.s-user-card--rep span.todo-no-class-here", None, "number")
    question["timestamp"] = extract_field(container, "time.s-user-card--time span.relativetime", "title", "date")
    return question

async def scrape_page(page_url: str) -> List[Dict[str, Any]]:
    html = await fetch_page(page_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select("div.s-post-summary.js-post-summary")
    questions = [parse_question(container) for container in containers]
    return questions

async def scrape_all_pages(base_url: str,
max_pages: int = 1) -> List[Dict[str, Any]]:
    all_questions = []
    for page in range(1, max_pages + 1):
        page_url = f"{base_url}?page={page}"
        questions = await scrape_page(page_url)
        if not questions:
            break
        all_questions.extend(questions)
    return all_questions

async def main():
    base_url = "https://stackoverflow.com/questions"
    questions = await scrape_all_pages(base_url, max_pages=3)
    print(json.dumps(questions, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
# === END OF FILE ===
