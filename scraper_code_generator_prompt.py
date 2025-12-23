from openrouter_client import openrouter_chat
import json


def generate_scraper_code(schema: dict, base_url: str) -> str:
    prompt = f"""
    ROLE:
    You are a senior web scraping engineer.

    INPUT:
    - Data schema (JSON below)
    - Target language: Python
    - Libraries: Playwright + BeautifulSoup
    - Rate limit: 1 request per second

    TASK:
    Generate production-ready scraping code that:
    1. Fetches pages
    2. Extracts data according to schema
    3. Handles missing fields safely
    4. Save JSON to a json file
    
    CONSTRAINTS:
    - No hardcoded indices
    - No global variables
    - Clear function boundaries
    - Libraries: Playwright (async) + BeautifulSoup
    - Fully functional
    - No placeholders; all functions and classes must be complete
    - Handle missing fields safely
    - Include pagination support if applicable
    - Include a main section (`if __name__ == "__main__":`) to run the scraper
    - It should at least scrap 10 pages if exist
    
    IMPORTANT:
    - Do not output explanations.
    - Do not truncate code.
    - If code is too long, split logically into functions or classes but still inside one ```python``` block.
    - Use the schema but make it usable by python (example: make null to None)
    - Use the base url
    - End the file with this exact line: # === END OF FILE ===
    
    OUTPUT:
    Only provide the Python code inside a single ```python``` block.

    BASE_URL:
    {base_url}

    SCHEMA:
    {json.dumps(schema, indent=2)}
    """
    response = openrouter_chat(prompt=prompt, model="mistralai/devstral-2512:free")
    return response


def complete_scraper_code(code: str, schema: dict) -> str:
    prompt = f"""
    ROLE:
    You are a senior web scraping engineer to complete the given code.
    
    TASK:
    Continue the Python code below from the exact cutoff point.

    RULES:
    - Do not make syntax errors since you wont be able to delete them
    - Use 4 spaces per level and never mix tabs and spaces.
    - Output ONLY Python code
    - Do NOT repeat any previous lines
    - Do NOT restart the file
    - Finish all open blocks
    - Ensure the file ends runnable
    - Use the schema but make it usable by python (example: make null to None)
    - End the file with only this exact line: # === END OF FILE ===

    
    SCHEMA:
    {json.dumps(schema, indent=2)}

    CODE SO FAR:
    {code}
    """
    response = openrouter_chat(prompt=prompt, model="mistralai/devstral-2512:free")
    return response


def fix_scraper_code(code: str, msg: str):
    prompt = f"""
        You generated Python code with a syntax error.

        Error:
        {msg}

        Rules:
        - Output ONLY valid Python code
        - NO explanations
        - NO markdown
        - Do NOT truncate
        - Preserve all working parts
        - Fix only the syntax error
        - Ensure the file ends cleanly

        Here is the broken code:
        {code}

    """
    response = openrouter_chat(prompt=prompt, model="mistralai/devstral-2512:free")
    return response
