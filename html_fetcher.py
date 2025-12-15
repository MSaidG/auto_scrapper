from typing import Literal, List
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup, Comment
from urllib.parse import urlparse, urljoin
from datetime import datetime




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


def validate_schema(schema: dict, html: str, base_url: str | None = None) -> dict:
    soup = BeautifulSoup(html, "lxml")

    result = {
        "valid": False,
        "confidence": 0.0,
        "containers_found": 0,
        "fields": {},
        "errors": [],
    }

    # 1️⃣ Find containers
    containers = soup.select(schema["container_selector"])
    result["containers_found"] = len(containers)

    if len(containers) < 2:
        result["errors"].append("Container selector returned < 2 elements")
        return result

    total_score = 0
    field_count = len(schema["fields"])

    # 2️⃣ Validate fields
    for field, spec in schema["fields"].items():
        matches = 0

        for c in containers:
            elements = c.select(spec["selector"])
            if not elements:
                continue

            el = elements[0]
            value = (
                el.get(spec["attribute"])
                if spec["attribute"]
                else el.get_text(strip=True)
            )

            if value:
                matches += 1

        coverage = matches / len(containers)
        ok = coverage >= 0.5  # threshold

        result["fields"][field] = {
            "ok": ok,
            "coverage": round(coverage, 2),
        }

        if ok:
            total_score += coverage
        else:
            result["errors"].append(f"Field '{field}' failed validation")

    # 3️⃣ Final score
    result["confidence"] = round(total_score / field_count, 2)
    result["valid"] = result["confidence"] >= 0.7

    return result


WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]



class HTMLFetcher:
    def __init__(
        self,
        timeout: int = 30_000,
        max_page_size: int = 3 * 1024 * 1024,
        user_agent: str | None = None,
        wait_until: WaitUntil = "networkidle",
        headless: bool = True,
    ):
        self.timeout = timeout
        self.max_page_size = max_page_size
        self.user_agent = user_agent or self._default_user_agent()
        self.wait_until: WaitUntil = wait_until  # ✅ CRITICAL
        self.headless = headless

    def fetch_html(self, url: str) -> str:
        self._validate_url(url)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(user_agent=self.user_agent)
            page = context.new_page()
            page.set_default_timeout(self.timeout)

            try:
                page.goto(url, wait_until=self.wait_until)
            except TimeoutError:
                pass  # partial content is OK

            html = page.content()
            browser.close()

        if len(html.encode("utf-8")) > self.max_page_size:
            html = html[: self.max_page_size]

        return html

    def extract_candidate_blocks(self, html: str, limit: int = 20) -> List[str]:
        """
        🔑 CRITICAL PART
        This is what you send to the LLM.
        """
        soup = BeautifulSoup(html, "lxml")

        # remove noise
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()

        blocks = soup.find_all(
            ["article", "li", "section", "div"],
            limit=limit,
        )

        return [str(b) for b in blocks if len(b.get_text(strip=True)) > 50]

    def _validate_url(self, url: str):
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

    def _default_user_agent(self) -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )


def infer_schema(blocks):
    try:
        return build_schema_prompt(blocks)
    except RuntimeError:
        return build_schema_prompt(blocks[:3])

fetcher = HTMLFetcher()

url = "https://quotes.toscrape.com/"
html = fetcher.fetch_html(url)
blocks = fetcher.extract_candidate_blocks(html)

print(f"HTML size: {len(html)}")
print(f"Blocks sent to LLM: {len(blocks)}")

# print(blocks[0][:500])


from schema_inferencer import build_schema_prompt
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
                candidate = text[start:i+1]
                return json.loads(candidate)

    raise ValueError("Unbalanced JSON braces")




blocks = fetcher.extract_candidate_blocks(html)

prompt = infer_schema(blocks)  # 🔑 5–20 blocks ONLY

raw_output = openrouter_chat(
    prompt=prompt,
    model= "mistralai/devstral-2512:free", # "mistralai/mistral-7b-instruct:free", # "mistralai/devstral-2512:free",
    # temperature=0.0,
)

# print("RAW MODEL OUTPUT: ")
# print(raw_output)
# print(raw_output[:1000])

schema = extract_json(raw_output)

print("SCHEMA")
print(schema)
print("")


validation = validate_schema(schema, html, base_url=url)

print("VALIDATION")
print(validation)
print("")

if not validation["valid"]:
    print("❌ Schema rejected, retry inference")
else:
    print("✅ Schema accepted")



data = extract_data(schema, html, base_url=url)

print("EXTRACTED DATA")
print(data[:2])
print("")


with open("output.json", "w", encoding="utf-8") as f:
    for item in data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print("Saved extracted data to output.json")
