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

import inspect

import re


def extract_python_code(ai_response: str) -> str:
    import re

    match = re.search(r"```python\s*([\s\S]*?)```", ai_response)
    if match:
        return match.group(1)
    return ai_response  # fallback if no fences


def clean_ai_code(ai_response: str) -> str:
    """
    Extract code from AI response, removing Markdown fences.
    """
    import re

    # Remove ```python ... ``` or ``` ... ```
    code = re.sub(r"^```python\s*|\s*```$", "", ai_response.strip(), flags=re.MULTILINE)
    code = re.sub(r"^```\s*|\s*```$", "", code.strip(), flags=re.MULTILINE)
    return code


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


import subprocess
import sys


def run_generated_file(path: str):
    result = subprocess.run([sys.executable, path], capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("Generated scraper crashed")

    print(result.stdout)


def save_code_to_file(code: str, filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"✅ Saved AI-generated scraper to {filename}")


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

def enforce_single_eof(code: str) -> str:
    sentinel = "# === END OF FILE ==="
    if sentinel not in code:
        return code

    first = code.index(sentinel)
    return code[: first + len(sentinel)] + "\n"

def has_multiple_main_blocks(code: str) -> bool:
    return code.count("if __name__ == \"__main__\"") > 1


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
            ["article", "li", "section", "div", "table", "thead", "tbody", "td"],
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


def infer_schema(blocks, endpoint_result):
    try:
        return build_schema_prompt(blocks, endpoint_result)
    except RuntimeError:
        return build_schema_prompt(blocks[:3], endpoint_result)


fetcher = HTMLFetcher()

# url = "https://quotes.toscrape.com/"
# url = "https://books.toscrape.com/"
# url = "https://quotes.toscrape.com/scroll"
# url = "https://quotes.toscrape.com/tableful"
url = "https://quotes.toscrape.com/random"

try_num = 15
html = fetcher.fetch_html(url)
blocks = fetcher.extract_candidate_blocks(html)

print(f"HTML size: {len(html)}")
print(f"Blocks sent to LLM: {len(blocks)}")


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


def complete_the_code(code: str, schema: dict) -> tuple[bool, str]:
    code = clean_ai_code(code)
    code = enforce_single_eof(code)
    
    
    if looks_truncated(code):
        print("LOOKS TRUNCATED!")

        continuation = complete_scraper_code(code, endpoint_result, schema)
        continuation = clean_ai_code(continuation)
        code += continuation
        return False, enforce_single_eof(code)

    try:
        compile(code, "<generated>", "exec")
        return True, enforce_single_eof(code)
    
    except SyntaxError as e:
        print("SYNTAX ERROR IN THE GENERATED CODE!")
        msg = (
            f"SyntaxError: {e.msg}\n"
            f"Line: {e.lineno}\n" 
            f"Text: {e.text}\n"
        )
        response = fix_scraper_code(code, msg)
        fixed_code = clean_ai_code(response)
        return False, enforce_single_eof(fixed_code)


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


def is_syntax_valid(code: str):
    try:
        compile(code, "<generated>", "exec")
        return True
    except SyntaxError as e:
        # print("SYNTAX ERROR IN THE GENERATED CODE!")
        msg = f"SyntaxError: {e.msg}\n" f"Line: {e.lineno}\n" f"Text: {e.text}"

        return False, msg



def looks_truncated(code: str) -> bool:
    sentinel = "# === END OF FILE ==="
    if sentinel in code:
        return False

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
        ":",
    )

    return stripped.endswith(bad_endings)


blocks = fetcher.extract_candidate_blocks(html)

from endpoint_classifier import EndpointClassifier  
import asyncio

endpoint_classifier = EndpointClassifier(url)
endpoint_result = asyncio.run(endpoint_classifier.classify())
print("ENDPPOINT RESULT")
print(endpoint_result)
print("")

prompt = infer_schema(blocks, endpoint_result)  # 🔑 5–20 blocks ONLY
raw_output = openrouter_chat(
    prompt=prompt,
    model="mistralai/devstral-2512:free",  # "mistralai/mistral-7b-instruct:free", # "mistralai/devstral-2512:free",
    # temperature=0.0,
)

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





# AI CODE GENERATED EXTRACTION
MAX_CONTINUATIONS = 5
ai_generated_code = clean_ai_code(generate_scraper_code(schema, endpoint_result, url))
for _ in range(MAX_CONTINUATIONS):
    is_completed, ai_generated_code = complete_the_code(
        ai_generated_code, schema
    )

    if is_completed:
        break
    


if not is_code_complete(ai_generated_code):
    filename = f"generated_scraper_quotes_{try_num}.py"
    genereted_code_filename = filename
    save_code_to_file(
        ai_generated_code, genereted_code_filename
    )  # generated_scrapper_code
    raise RuntimeError("Failed to generate complete code")

filename = f"generated_scraper_quotes_{try_num}.py"
genereted_code_filename = filename
save_code_to_file(
    ai_generated_code, genereted_code_filename
)  # generated_scrapper_code
run_generated_file(genereted_code_filename)


