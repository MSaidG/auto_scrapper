from typing import List
from typing import List, Dict, Any
import json

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
- Use ENDPOINT CONTEXT to avoid fields that cannot exist
  (e.g., pagination fields for random endpoints)

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

def build_schema_prompt(
    blocks: List[str],
    endpoint_result: Dict[str, Any]
) -> str:
    """
    Builds the final prompt sent to the LLM.
    """

    html_section = "\n\n".join(
        f"### BLOCK {i+1}\n{block}"
        for i, block in enumerate(blocks)
    )

    endpoint_section = json.dumps(endpoint_result, indent=2)

    return f"""{SCHEMA_INFERENCE_PROMPT}

      ENDPOINT CONTEXT (for guidance only):
      {endpoint_section}

      HTML SNIPPETS:
      {html_section}
    
    """
