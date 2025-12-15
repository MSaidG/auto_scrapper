import requests
import os
from dotenv import load_dotenv

load_dotenv()  

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY not set")

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def openrouter_chat(prompt: str, model: str):
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",  # REQUIRED
            "X-Title": "auto-scraper",
        },
        json={
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 800,   # IMPORTANT
        },
        timeout=60,
    )

    response.raise_for_status()
    data = response.json()
    
    # print("FULL OPENROUTER RESPONSE:")
    # print(data)
    
    # content = data["choices"][0]["message"]["content"]
    
    
    if "choices" not in data:
        raise RuntimeError(f"OpenRouter error response: {data}")

    if not data["choices"]:
        raise RuntimeError(f"OpenRouter returned empty choices: {data}")

    message = data["choices"][0].get("message")
    if not message or "content" not in message:
        raise RuntimeError(f"Malformed OpenRouter response: {data}")

    content = message["content"]
    if not content.strip():
        raise RuntimeError("Model returned empty content")
    
    
    return content
