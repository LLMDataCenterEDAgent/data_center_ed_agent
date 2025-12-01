# agents/parsing_agent.py

from openai import OpenAI
import json
from utils.json_cleaner import extract_json_like
from utils.parser_prompt import PARSING_SYSTEM_PROMPT
from state.schemas import GeneratorSpec, EDParams
from utils.demand_extractor import extract_demand_from_text
client = OpenAI()

def normalize_generator_keys(parsed_json: dict):
    """
    LLM이 잘못된 key(G1,G2 대신 generator1 등)를 넣었을 때 교정해주는 함수
    """

    # Case 1: 올바른 구조면 그대로 사용
    if "generators" in parsed_json:
        return parsed_json

    # Case 2: G1, G2 구조일 때
    if "G1" in parsed_json and "G2" in parsed_json:
        return {
            "generators": {
                "G1": parsed_json["G1"],
                "G2": parsed_json["G2"],
            },
            "demand": parsed_json.get("demand")
        }

    # Case 3: generator1, generator2 등 엉뚱한 이름일 때
    possible_names = ["generator1", "generator2", "gen1", "gen2"]
    found = [k for k in parsed_json.keys() if k.lower() in possible_names]

    if len(found) >= 2:
        return {
            "generators": {
                "G1": parsed_json[found[0]],
                "G2": parsed_json[found[1]],
            },
            "demand": parsed_json.get("demand")
        }

    raise ValueError(f"Cannot normalize generator keys: {parsed_json}")


def parse_problem(text: str) -> EDParams:

    # 1) 먼저 한국어 → 영어 변환
    translation_resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "Translate to English while preserving ALL numbers exactly."},
            {"role": "user", "content": text},
        ],
        temperature=0
    )
    english_text = translation_resp.choices[0].message.content

    # 2) JSON 파싱 시도
    attempts = 0
    last_json = None

    while attempts < 3:
        attempts += 1

        parsing_resp = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": PARSING_SYSTEM_PROMPT},
                {"role": "user", "content": english_text},
            ],
            temperature=0
        )

        raw = parsing_resp.choices[0].message.content
        last_json = raw

        parsed_json = extract_json_like(raw)
        parsed_json = normalize_generator_keys(parsed_json)

        demand = parsed_json.get("demand")

        # 🔥 Case 1: demand를 LLM이 숫자 문자열로 뽑았을 때
        if isinstance(demand, str):
            # "500MW" → 500
            num = extract_demand_from_text(demand)
            if num is not None:
                demand = num

        # 🔥 Case 2: demand가 None이면 fallback으로 “문제 텍스트 전체”에서 숫자 추출
        if demand is None:
            demand = extract_demand_from_text(text)

        # 🔥 Case 3: 그래도 None? 영어 텍스트 fallback
        if demand is None:
            demand = extract_demand_from_text(english_text)

        # 🔥 demand가 숫자로 잘 잡혔다면 OK
        if demand is not None:
            # generators 처리
            generators = {}
            for name, vals in parsed_json["generators"].items():
                generators[name] = GeneratorSpec(name=name, **vals)

            return EDParams(generators=generators, demand=demand)

        print(f"[WARN] attempt {attempts} - demand still None")

    # 3) 최종 실패 시 raw JSON 출력 후 에러
    print("==== RAW JSON FROM LLM ====")
    print(last_json)
    print("===========================")

    raise ValueError("Parsing failed: demand missing even after fallback.")