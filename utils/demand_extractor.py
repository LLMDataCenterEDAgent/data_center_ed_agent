# utils/demand_extractor.py
import re

def extract_demand_from_text(text: str):
    """
    '500MW', '500 MW', 'demand is 500MW' 등 모든 형태에서 숫자만 뽑아 float로 반환.
    """
    matches = re.findall(r"\d+\.?\d*", text)
    if not matches:
        return None
    # 가장 마지막 숫자가 demand인 경우가 대부분
    return float(matches[-1])
