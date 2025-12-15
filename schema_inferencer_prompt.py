import json
from typing import List


SCHEMA_INFERENCE_PROMPT = """
ROLE:
You are a web data analyst specializing in reverse-engineering website structures.

TASK:
Given HTML snippets from a webpage, identify:
1. The main repeating data entity (if any)
2. The fields inside each entity
3. Robust CSS or XPath selectors for each field
4. The expected data type of each field

RULES:
- Do NOT generate scraping code
- Prefer stable selectors (avoid dynamic IDs)
- Assume the site structure may change slightly

OUTPUT FORMAT (JSON ONLY):
{
  "entity": "...",
  "container_selector": "...",
  "fields": {
    "field_name": {
      "selector": "...",
      "attribute": null | "href" | "src",
      "type": "string | number | date | url"
    }
  }
}
"""

def build_schema_prompt(blocks: List[str]) -> str:
    """
    Builds the final prompt sent to the LLM.
    """
    html_section = "\n\n".join(
        f"### BLOCK {i+1}\n{block}"
        for i, block in enumerate(blocks)
    )

    return f"""{SCHEMA_INFERENCE_PROMPT}

HTML SNIPPETS:
{html_section}
"""
