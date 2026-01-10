from scraper_code_generator_prompt import (
    generate_scraper_code,
    complete_scraper_code,
    fix_scraper_code,
)
from typing import Literal, List
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup, Comment
from urllib.parse import urlparse, urljoin
from datetime import datetime

from endpoint_classifier import EndpointClassifier
import asyncio

import inspect
import subprocess
import sys

import re


def run_generated_file(path: str):
    print(f"🚀 Running {path}...")
    result = subprocess.run([sys.executable, path], capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ Scraper crashed:")
        print(result.stderr)
        # return False # Could trigger retry here
    else:
        print("🎉 Scraper finished successfully:")
        print(result.stdout)
        # return True


def save_code_to_file(code: str, filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"✅ Saved AI-generated scraper to {filename}")


def run_ai_scraper(code: str, url: str):
    namespace = {}
    exec(code, namespace)

    # Discover a function that accepts a URL
    import inspect

    for obj in namespace.values():
        if callable(obj):
            sig = inspect.signature(obj)
            if len(sig.parameters) >= 1:
                try:
                    data = obj(url)
                    if isinstance(data, list):
                        print(data[:2])
                        return data
                except Exception:
                    continue

    raise RuntimeError(
        "No suitable scraper function found TRY RUNNING GENERATED CODE MANUALLY"
    )


def find_scraper_function(namespace):
    candidates = []
    for name, obj in namespace.items():
        if callable(obj):
            # check if it has at least 1 parameter (the URL)
            sig = inspect.signature(obj)
            if len(sig.parameters) >= 1:
                candidates.append((name, obj))
    if not candidates:
        raise RuntimeError("No suitable scraper function found in AI code")
    # Choose the first candidate for now
    return candidates[0][1]


def cast_value(value: str, dtype: str):
    if value is None:
        return None

    try:
        if dtype == "number":
            return float(value)
        if dtype == "date":
            return datetime.fromisoformat(value)
        return value
    except Exception:
        return value


def extract_data(schema: dict, html: str, base_url: str | None = None) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results = []

    containers = soup.select(schema["container_selector"])

    for c in containers:
        item = {}

        for field, spec in schema["fields"].items():
            elements = c.select(spec["selector"])

            values = []
            for el in elements:
                if spec.get("attribute"):
                    attr = el.get(spec["attribute"])

                    if isinstance(attr, list):
                        val = attr[0] if attr else None
                    else:
                        val = attr

                    if isinstance(val, str) and base_url:
                        val = urljoin(base_url, val)
                else:
                    val = el.get_text(strip=True)

                if val:
                    values.append(cast_value(val, spec.get("type", "string")))

            # Handle single vs multi value
            if not values:
                item[field] = None
            elif spec.get("type", "").endswith("[]"):
                item[field] = values
            else:
                item[field] = values[0]

        # Keep only non-empty rows
        if any(v is not None for v in item.values()):
            results.append(item)

    return results


def validate_schema(schema, html, endpoint_type="DEFAULT"):
    soup = BeautifulSoup(html, "lxml")

    containers = soup.select(schema["container_selector"])
    if not containers:
        return {"valid": False, "reason": "No containers"}

    min_coverage = {
        "RANDOM": 0.1,
        "SCROLL": 0.3,
        "PAGINATION": 0.3,
        "TABLE": 0.1,
        "DEFAULT": 0.5,
    }.get(endpoint_type, 0.5)

    field_scores = []
    for field, spec in schema["fields"].items():
        matches = 0
        for c in containers:
            el = c.select_one(spec["selector"])
            if el:
                matches += 1

        coverage = matches / len(containers)
        field_scores.append(coverage)

    confidence = sum(field_scores) / len(field_scores)
    return {
        "valid": confidence >= min_coverage,
        "confidence": round(confidence, 2),
        "containers_found": len(containers),
    }


def has_multiple_main_blocks(code: str) -> bool:
    return code.count('if __name__ == "__main__"') > 1


WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]


class HTMLFetcher:
    def __init__(
        self,
        timeout: int = 30_000,
        max_page_size: int = 3 * 1024 * 1024,  # 3MB
        user_agent: str | None = None,
        wait_until: WaitUntil = "domcontentloaded",  # Changed default to faster load
        headless: bool = True,
    ):
        self.timeout = timeout
        self.max_page_size = max_page_size
        self.user_agent = user_agent or self._default_user_agent()
        self.wait_until: WaitUntil = wait_until
        self.headless = headless

    def fetch_html(self, url: str) -> str:
        self._validate_url(url)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1280, "height": 1024},  # Ensure desktop view
            )
            page = context.new_page()
            page.set_default_timeout(self.timeout)

            try:
                page.goto(url, wait_until=self.wait_until)

                # Scroll to bottom to trigger lazy loading (crucial for "scrape everything")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)  # Wait for lazy load

            except TimeoutError:
                logger.warning("Page load timed out, processing partial content.")

            html = page.content()
            browser.close()

        # DOM-safe size limiting
        soup = BeautifulSoup(html, "lxml")

        # Remove explicitly useless tags first
        for tag in soup(["script", "style", "noscript", "svg", "iframe", "canvas"]):
            tag.decompose()

        current_size = len(str(soup).encode("utf-8"))
        if current_size > self.max_page_size:
            # If still too big, remove comments
            for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
                c.extract()

        return str(soup)

    def extract_candidate_blocks(self, html: str, limit: int = 15) -> List[str]:
        """
        Extracts relevant HTML blocks for the AI to analyze.
        """
        soup = BeautifulSoup(html, "lxml")

        # Clean again just in case
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        # Identify potential content containers
        # We look for containers that wrap the items we want
        candidates = soup.find_all(
            ["article", "section", "div", "table", "tbody", "ul", "main"],
        )

        scored = []
        for tag in candidates:
            # Skip if purely navigation
            if is_navigation_block(tag):
                continue

            # Skip if explicitly hidden
            if "display:none" in str(tag.get("style", "")).replace(" ", "").lower():
                continue

            # Get text for length check
            text = tag.get_text(strip=True)

            # Allow shorter blocks if they contain images (e.g. product cards)
            if len(text) < 30 and not tag.find("img"):
                continue

            score = score_content_block(tag)

            # If a block is VERY large, it might be the 'body' or 'html' tag.
            # We prefer specific sections over the whole page, unless specific sections are weak.
            if len(str(tag)) > 100_000:
                score *= 0.5  # Penalize wrapper-of-everything

            scored.append((score, tag))

        # Sort by score
        scored.sort(key=lambda x: x[0], reverse=True)

        # De-duplicate nested blocks
        # If Block A contains Block B, and both are high score, we might only want Block A
        final_blocks = []
        seen_content = set()

        for score, tag in scored[: limit * 2]:  # Check top 2x limit
            content_hash = hash(str(tag)[:500])  # approximate hash
            if content_hash in seen_content:
                continue

            seen_content.add(content_hash)
            final_blocks.append(str(tag))

            if len(final_blocks) >= limit:
                break

        return final_blocks

    def _validate_url(self, url: str):
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

    def _default_user_agent(self) -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        )


def infer_schema(blocks, endpoint_result):
    try:
        return build_schema_prompt(blocks, endpoint_result)
    except RuntimeError:
        return build_schema_prompt(blocks[:3], endpoint_result)


try_num = 24

from schema_inferencer_prompt import build_schema_prompt
from openrouter_client import openrouter_chat
import json

import re


def extract_json(text: str) -> dict:
    """
    Robustly extract the first valid JSON object from LLM output.
    Handles:
    - Markdown fences
    - Multiple JSON blocks
    - Nested objects
    """

    # 1. Prefer fenced ```json blocks
    fenced = re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    for block in fenced:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass  # try next

    # 2. Fallback: brace-balanced extraction
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                return json.loads(candidate)

    raise ValueError("Unbalanced JSON braces")


# def enforce_single_eof(code: str) -> str:
#     sentinel = "# === END OF FILE ==="
#     if sentinel not in code:
#         return code

#     first = code.index(sentinel)
#     return code[: first + len(sentinel)] + "\n"


# def complete_the_code(code: str, schema: dict) -> tuple[bool, str]:
#     code = clean_ai_code(code)
#     code = enforce_single_eof(code)


#     if looks_truncated(code):
#         print("LOOKS TRUNCATED!")

#         continuation = complete_scraper_code(code, endpoint_result, schema)
#         continuation = clean_ai_code(continuation)
#         code += continuation
#         return False, enforce_single_eof(code)

#     try:
#         compile(code, "<generated>", "exec")
#         return True, enforce_single_eof(code)

#     except SyntaxError as e:
#         print("SYNTAX ERROR IN THE GENERATED CODE!")
#         msg = (
#             f"SyntaxError: {e.msg}\n"
#             f"Line: {e.lineno}\n"
#             f"Text: {e.text}\n"
#         )
#         response = fix_scraper_code(code, msg)
#         fixed_code = clean_ai_code(response)
#         return False, enforce_single_eof(fixed_code)

def clean_ai_code(ai_response: str) -> str:
    code = re.sub(r"^```python\s*|\s*```$", "", ai_response.strip(), flags=re.MULTILINE)
    code = re.sub(r"^```\s*|\s*```$", "", code.strip(), flags=re.MULTILINE)
    return code


def enforce_single_eof(code: str) -> str:
    sentinel = "# === END OF FILE ==="

    # If the marker appears multiple times, take the first one and cut strictly
    if sentinel in code:
        first_index = code.index(sentinel)
        # Cut exactly at the end of the sentinel
        clean_code = code[: first_index + len(sentinel)]
        return clean_code + "\n"

    return code


# def clean_ai_code(ai_response: str) -> str:
#     """
#     Extract code from AI response, removing Markdown fences.
#     """
#     # 1. If strict Python fence exists, prioritize it
#     match = re.search(r"```python\s*([\s\S]*?)```", ai_response)
#     if match:
#         return match.group(1).strip()

#     # 2. Remove generic fences
#     code = re.sub(r"^```\s*|\s*```$", "", ai_response.strip(), flags=re.MULTILINE)

#     # 3. CRITICAL FIX: If the output looks like a JSON object (starts/ends with braces)
#     # and we expected Python, the AI failed. We try to salvage or return as is.
#     # (But usually, we just want to strip whitespace).
#     return code.strip()


def complete_the_code(code: str, schema: dict) -> tuple[bool, str]:
    code = clean_ai_code(code)

    # 1. Immediate Cutoff: If EOF is present, discard any trailing garbage (like JSON)
    code = enforce_single_eof(code)

    # 2. Check if we actually need to continue
    if not looks_truncated(code):
        # Even if not truncated, ensure it compiles
        if is_syntax_valid(code):
            return True, code

    print("⚠️ Code looks truncated. Asking AI to complete it...")

    # 3. Generate Continuation
    continuation = complete_scraper_code(code, endpoint_result, schema)
    continuation = clean_ai_code(continuation)

    # --- SAFETY CHECK: Did the AI give us JSON instead of Code? ---
    if continuation.strip().startswith("{") and ":" in continuation:
        print("❌ AI returned JSON instead of Python code. Ignoring this continuation.")
        # We return False to stop the loop or try a different fix,
        # but strictly DO NOT append the JSON.
        return False, code
    # -------------------------------------------------------------

    # 4. Append and Re-process
    full_code = code + "\n" + continuation
    full_code = enforce_single_eof(
        full_code
    )  # Cut off again in case AI added EOF + Garbage

    if is_syntax_valid(full_code):
        return True, full_code

    return False, full_code


def is_syntax_valid(code: str):
    try:
        compile(code, "<generated>", "exec")
        return True
    except SyntaxError as e:
        msg = f"SyntaxError: {e.msg}\n" f"Line: {e.lineno}\n" f"Text: {e.text}"
        return False, msg


def is_code_complete(code: str) -> bool:
    code = clean_ai_code(code)
    code = enforce_single_eof(code)

    if looks_truncated(code):
        return False

    try:
        compile(code, "<generated>", "exec")
        return True
    except SyntaxError as e:
        print(f"SyntaxError at line {e.lineno}: {e.msg}")
        return False


from scraper_code_generator_prompt import (
    generate_scraper_code,
    complete_scraper_code,
    fix_scraper_code,
)
from typing import Literal, List, Optional
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup, Comment, Tag
from urllib.parse import urlparse, urljoin
from datetime import datetime

from endpoint_classifier import EndpointClassifier
import asyncio
import inspect
import re
import json
import sys
import subprocess
import logging

# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def is_category_tree(tag: Tag) -> bool:
    """
    Detect hierarchical category / taxonomy structures.
    IMPROVED: Distinguish between sidebars (bad) and main content lists (good).
    """
    # If it contains images, it's likely a product list, not a text-only category tree
    if tag.find("img"):
        return False

    # Must contain lists
    lists = tag.find_all(["ul", "ol"])
    if not lists:
        return False

    li_items = tag.find_all("li")
    if len(li_items) < 3:
        return False

    # Check for "link density" specifically in the LIs
    nav_keywords = [
        "category",
        "categories",
        "department",
        "browse",
        "refine",
        "filter",
    ]
    header_text = tag.find(["h1", "h2", "h3", "h4"])
    if header_text and any(k in header_text.get_text().lower() for k in nav_keywords):
        return True

    return False


def is_navigation_block(tag: Tag) -> bool:
    """
    Heuristic detection of navigation / boilerplate blocks.
    IMPROVED: Does not filter out Grids/Lists that happen to be links.
    """
    text = tag.get_text(" ", strip=True).lower()
    links = tag.find_all("a")
    imgs = tag.find_all("img")

    text_len = len(text)

    # If it has significant images, it's likely content (e.g. product grid), not nav
    if len(imgs) > 2:
        return False

    # Pure menu lists (nav, header, footer usually contain strict navigation)
    if tag.name in {"nav", "footer"}:  # Removed 'header' as sometimes h1 is inside
        return True

    # Too many links, too little text, AND no images
    if links and text_len < 200 and len(links) >= 3 and not imgs:
        return True

    # Keyword check
    nav_keywords = [
        "login",
        "register",
        "my account",
        "sign in",
        "sign up",
        "logout",
        "terms of use",
        "privacy policy",
        "copyright",
        "sitemap",
        "facebook",
        "twitter",
        "instagram",
        "linkedin",
        "follow us",
        "account",
        "profile",
        "wishlist",
        "favorite",
        "cart",
        "basket",
        "checkout",
        "sipariş",
        "alışveriş",
        "favori",
    ]

    # Check if a significant portion of text matches nav keywords
    matches = sum(1 for k in nav_keywords if k in text)
    if matches >= 2:
        return True

    return False


def score_content_block(tag: Tag) -> float:
    """
    Scores a block based on likelihood of being valuable content.
    IMPROVED: Rewards repeating structures (lists/tables).
    """
    text = tag.get_text(" ", strip=True)
    text_len = len(text)
    if text_len == 0:
        return 0.0

    links = tag.find_all("a")
    imgs = tag.find_all("img")
    rows = tag.find_all(["tr", "li", "article", "div"])

    score = 0.0

    # 1. Text Volume (capped)
    score += min(text_len / 200, 5.0)

    # 2. Visual Content (Images are high value for scraping)
    score += len(imgs) * 2.0

    # 3. Structure / Repetition (The "Scrape Everything" heuristic)
    # If a block has many children of the same tag, it's likely a list of data.
    child_tags = [child.name for child in tag.find_all(recursive=False) if child.name]
    if child_tags:
        most_common = max(set(child_tags), key=child_tags.count)
        count = child_tags.count(most_common)
        if count > 3:
            score += count * 1.5  # Reward lists!

    # 4. Link Density Adjustment
    # Only penalize links if there are NO images and NO structure
    link_text_len = sum(len(a.get_text(strip=True)) for a in links)
    link_ratio = link_text_len / text_len

    if link_ratio > 0.7 and len(imgs) == 0:
        score -= 5.0  # Heavy penalty for pure link lists (footers/navs)

    return score


# ... [Keep extract_python_code, clean_ai_code, run_ai_scraper as they are] ...
def extract_python_code(ai_response: str) -> str:
    import re

    match = re.search(r"```python\s*([\s\S]*?)```", ai_response)
    if match:
        return match.group(1)
    return ai_response


# ... [Keep file operations and validation logic] ...


# ... [Keep extract_json, complete_the_code logic] ...


def looks_truncated(code: str) -> bool:
    sentinel = "# === END OF FILE ==="
    if sentinel in code:
        return False

    # Check for unclosed parentheses/brackets by counting
    if code.count("(") > code.count(")"):
        return True
    if code.count("[") > code.count("]"):
        return True
    if code.count("{") > code.count("}"):
        return True

    stripped = code.rstrip()
    bad_endings = (
        "def ",
        "class ",
        "async def ",
        "if ",
        "for ",
        "while ",
        "=",
        "(",
        "[",
        "{",
        ",",
        ":",
        "return",
        "import",
        "from",
    )
    return stripped.endswith(bad_endings)




# ... [Main Execution Block] ...


# url = "https://quotes.toscrape.com/"
# url = "https://quotes.toscrape.com/scroll"
# url = "https://quotes.toscrape.com/random"
# url = "https://quotes.toscrape.com/tableful/"
# url = "https://www.gutenberg.org/ebooks/search/"
# url = "https://books.toscrape.com/" ## ADDED
# url = "https://www.kitapyurdu.com/index.php?route=product%2Fbest_sellers&list_id=729&filter_in_shelf=0&filter_in_stock=0" ## ADDED
# url = "https://news.ycombinator.com/"
# url = "https://www.rottentomatoes.com/browse/tv_series_browse/sort:popular"
# url = "https://www.scrapethissite.com/pages/simple/"
# url = "https://www.scrapethissite.com/pages/forms/"
# url = "https://www.scrapethissite.com/pages/forms/?page_num=1"
# url = "https://www.mcmaster.com/"
url = ""


# url = "https://www.imdb.com/chart/top/"
# url = "https://stackoverflow.com/questions?page=1"
# url = "https://medium.com/tag/web-development"
# url = "https://www.reddit.com/r/webdev/"


# url = "https://www.iana.org/protocols"
# url = "https://www.facebook.com/"
# url = "https://x.com/"
# url = "https://quotes.toscrape.com/search.aspx"


# ----------------------------
# MAIN EXECUTION
# ----------------------------

if __name__ == "__main__":
    from schema_inferencer_prompt import build_schema_prompt
    from openrouter_client import openrouter_chat

    print(f"🌐 Fetching: {url}")
    fetcher = HTMLFetcher(headless=True)  # Set headless=True for production
    html = fetcher.fetch_html(url)

    print("🔍 Extracting candidate blocks...")
    blocks = fetcher.extract_candidate_blocks(html)
    print(f"found {len(blocks)} candidate blocks")

    endpoint_classifier = EndpointClassifier(url)
    endpoint_result = asyncio.run(endpoint_classifier.classify())
    print(f"📊 Endpoint Type: {endpoint_result.get('type')}")

    # Infer Schema
    print("🤖 Inferring Schema...")
    prompt = infer_schema(blocks, endpoint_result)
    

    # Retry loop for schema generation
    schema = None
    for attempt in range(3):
        try:
            raw_output = openrouter_chat(
                prompt=prompt,
                model="mistralai/devstral-2512:free",  # Use a strong model
            )
            schema = extract_json(raw_output)
            break
        except Exception as e:
            print(f"Schema generation failed (attempt {attempt+1}): {e}")

    if not schema:
        raise RuntimeError("Could not generate schema")

    print("SCHEMA:", json.dumps(schema, indent=2))

    # Validate Schema
    validation = validate_schema(schema, html, endpoint_result["type"])
    if not validation["valid"]:
        print(f"⚠️ Validation Warning: {validation}")
        # We proceed anyway because user prefers 'scraping something' over 'nothing'
    else:
        print("✅ Schema validated")

    # Generate Code
    print("👨‍💻 Generating Scraper Code...")
    ai_generated_code = clean_ai_code(
        generate_scraper_code(schema, endpoint_result, url)
    )

    # Fix Loop
    MAX_CONTINUATIONS = 10
    for _ in range(MAX_CONTINUATIONS):
        is_completed, ai_generated_code = complete_the_code(ai_generated_code, schema)
        if is_completed:
            break

    # Save and Run
    try_num = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"generated_scraper_{try_num}.py"
    save_code_to_file(ai_generated_code, filename)

    run_generated_file(filename)
