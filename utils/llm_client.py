# utils/llm_client.py
import os
from openai import OpenAI

def get_llm_client():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("Set OPENAI_API_KEY first.")
    return OpenAI(api_key=key)