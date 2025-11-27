# core/llm.py

import os
from openai import OpenAI

# 환경변수에서 API 키 읽기
if "OPENAI_API_KEY" not in os.environ:
    raise RuntimeError(
        "환경변수 OPENAI_API_KEY가 설정되어 있지 않습니다.\n"
        "export OPENAI_API_KEY=your_key 또는 setx OPENAI_API_KEY your_key"
    )

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def call_llm(system_prompt: str, user_prompt: str, model: str = "gpt-4.1-mini") -> str:
    """OpenAI Responses API 호출 함수"""
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.output[0].content[0].text
