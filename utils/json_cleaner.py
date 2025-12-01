# utils/json_cleaner.py
import json
import re

def extract_json_like(text: str):
    """
    LLM 출력에서 JSON만 깔끔하게 추출하는 함수.
    JSON 앞뒤에 붙은 설명/문자 제거.
    """
    if text is None:
        raise ValueError("LLM returned empty response.")

    # JSON 블록만 추출하는 정규식
    json_pattern = r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}"
    match = re.search(json_pattern, text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find JSON in text:\n{text}")

    cleaned = match.group(0)

    # JSON 파싱
    return json.loads(cleaned)
