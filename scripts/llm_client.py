# scripts/llm_client.py

import os
from openai import OpenAI

def get_openrouter_client():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://forgedbyfreedom.com",
            "X-Title": "Forged By Freedom AI"
        }
    )
