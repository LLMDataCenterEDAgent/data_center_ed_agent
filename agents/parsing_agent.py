# agents/parsing_agent.py

from openai import OpenAI
import json
from utils.json_cleaner import extract_json_like
from utils.parser_prompt import PARSING_SYSTEM_PROMPT
from state.schemas import GeneratorSpec, EDParams
from utils.demand_extractor import extract_demand_from_text

client = OpenAI()

# --- 기존 헬퍼 함수들 (Step 1 텍스트 파싱용) ---

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

    # 정규화 실패 시 원본 반환 (이후 검증 로직에서 처리)
    return parsed_json


def parse_problem(text: str) -> EDParams:
    # 1) 먼저 한국어 → 영어 변환
    translation_resp = client.chat.completions.create(
        model="gpt-4o",  # 최신 모델 사용 권장
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
            model="gpt-4o",
            messages=[
                {"role": "system", "content": PARSING_SYSTEM_PROMPT},
                {"role": "user", "content": english_text},
            ],
            temperature=0
        )

        raw = parsing_resp.choices[0].message.content
        last_json = raw

        try:
            parsed_json = extract_json_like(raw)
            parsed_json = normalize_generator_keys(parsed_json)

            demand = parsed_json.get("demand")

            # 🔥 Case 1: demand를 LLM이 숫자 문자열로 뽑았을 때
            if isinstance(demand, str):
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
                if "generators" in parsed_json:
                    for name, vals in parsed_json["generators"].items():
                        generators[name] = GeneratorSpec(name=name, **vals)

                    return EDParams(generators=generators, demand=demand)
        except Exception as e:
            print(f"[WARN] parsing attempt {attempts} failed: {e}")

    # 3) 최종 실패 시 raw JSON 출력 후 에러
    print("==== RAW JSON FROM LLM ====")
    print(last_json)
    print("===========================")

    raise ValueError("Parsing failed: demand missing even after fallback.")


# --- 메인 Agent 클래스 (수정된 부분) ---

class ParsingAgent:
    def run(self, state: dict):
        print("\n--- Parsing Agent Started ---")

        # [핵심] 이미 main.py에서 주입한 데이터(params)가 있으면 LLM 파싱을 건너뜀
        # 이렇게 해야 Step 2(시계열 데이터)가 날아가지 않음
        if state.get("params") is not None:
            print(">> Structured data detected in 'params'. Skipping LLM parsing.")
            return state

        # 데이터가 없으면 텍스트(Step 1 방식)를 파싱
        problem_text = state.get("problem_text", "")
        if not problem_text:
            print(">> No problem text provided.")
            return state

        print(f">> Parsing text with LLM: {problem_text[:50]}...")
        
        try:
            # 텍스트 파싱 결과(EDParams 객체)를 딕셔너리로 변환하여 저장
            ed_params = parse_problem(problem_text)
            
            # Pydantic 객체 -> Dict 변환 (하위 호환성 유지)
            # 만약 Formulation Agent가 객체를 처리하도록 되어있으면 이 부분 조정 필요
            # 여기서는 편의상 dict로 변환하여 저장
            if hasattr(ed_params, "model_dump"):
                state["params"] = ed_params.model_dump()
            else:
                state["params"] = ed_params.dict()
                
            print(">> Text parsing completed.")
            
        except Exception as e:
            print(f">> Parsing Error: {e}")
            state["params"] = None

        return state