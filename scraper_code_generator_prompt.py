from openrouter_client import openrouter_chat
from typing import Dict, Any
import json


def generate_scraper_code(schema: dict, endpoint_result: Dict[str, Any], base_url: str) -> str:
    prompt = f"""
    ROLE:
    You are a senior web scraping engineer.

    INPUT:
    - Data schema (JSON below)
    - Target language: Python
    - Libraries: Playwright + BeautifulSoup
    - Rate limit: 1 request per second
    
    RULES:
    - DO NOT assume pagination unless explicitly stated
    - For random endpoints, repeat requests N times
    - Do NOT scroll unless endpoint_type is "scroll"
    - Prefer deterministic waits over sleeps

    TASK:
    Generate production-ready Python code that:
    - Uses Playwright (async) and BeautifulSoup
    - Scrapes data according to the schema
    - Handles missing fields safely
    - Support pagination
    - Saves output to a JSON file
    - Is fully runnable
    
    CONSTRAINTS:
    - No markdown
    - No backticks
    - No explanations
    - No placeholders
    - No global variables
    - Clear function boundaries
    - Use base_url
    - Convert JSON null → Python None
    - Ensure all brackets, quotes, and blocks are closed
    - Include a main section (`if __name__ == "__main__":`) to run the scraper
    - End the file with exactly: # === END OF FILE ===

    BASE_URL:
    {base_url}

    SCHEMA:
    {json.dumps(schema, indent=2)}
    
    ENDPOINT CONSTRAINTS (MANDATORY):
    {json.dumps(endpoint_result, indent=2)}
    """
    response = openrouter_chat(prompt=prompt, model="mistralai/devstral-2512:free")
    return response


def complete_scraper_code(code: str, endpoint_result: Dict[str, Any], schema: dict) -> str:
    prompt = f"""
        ROLE:
        You are completing a partially generated Python file.

        TASK:
        Continue the code below and make it fully valid and runnable.

        RULES:
        - Output ONLY Python code
        - No markdown, no explanations
        - You may repeat the last 5 lines if needed
        - Do NOT restart the file
        - Close all open blocks
        - Convert JSON null → Python None
        - End with exactly: # === END OF FILE ===

        SCHEMA:
        {json.dumps(schema, indent=2)}
        
        ENDPOINT CONSTRAINTS (MANDATORY):
        {json.dumps(endpoint_result, indent=2)}

        CODE SO FAR:
        {code}
    """
    return openrouter_chat(prompt=prompt, model="mistralai/devstral-2512:free")


def fix_scraper_code(code: str, msg: str):
    prompt = f"""
        ROLE:
        You are fixing a Python syntax error.

        ERROR DETAILS:
        {msg}

        RULES:
        - Output ONLY valid Python code
        - No markdown
        - No explanations
        - Preserve all correct logic
        - Fix ONLY the syntax issue
        - Ensure file ends cleanly with: # === END OF FILE ===

        BROKEN CODE:
        {code}
    """
    
    return openrouter_chat(prompt=prompt, model="mistralai/devstral-2512:free")
