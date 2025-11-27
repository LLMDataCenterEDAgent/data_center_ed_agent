# agents/data_extractor_agent.py

import re
from core.state import EDAgentState

def parse_number(text):
    nums = re.findall(r"\d+\.?\d*", text)
    return float(nums[0]) if nums else None


def data_extractor_node(state: EDAgentState) -> EDAgentState:
    scenario = state.scenario

    # -----------------------------
    # 1) 기본 Load (피크 부하)
    # -----------------------------
    base_load_match = re.search(r"부하는\s*(\d+)\s*MW", scenario)
    base_load = float(base_load_match.group(1)) if base_load_match else 10.0

    load_profile = [base_load] * 24

    # 시간대 부하 증가
    inc_match = re.search(r"(\d+)~(\d+)시에.*?(\d+)%\s*상승", scenario)
    if inc_match:
        start = int(inc_match.group(1))
        end = int(inc_match.group(2))
        pct = int(inc_match.group(3))
        for t in range(start, end + 1):
            load_profile[t] = base_load * (1 + pct / 100)

    # -----------------------------
    # 2) ESS 파라미터
    # -----------------------------
    ess_cap = parse_number(re.search(r"ESS는\s*(\d+)\s*MWh", scenario).group()) if "ESS" in scenario else 20
    ess_p = parse_number(re.search(r"최대\s*충/방전\s*(\d+)\s*MW", scenario).group()) if "충/방전" in scenario else 5

    soc_range = re.search(r"SOC\s*(\d+)~(\d+)%", scenario)
    soc_min = int(soc_range.group(1))/100 if soc_range else 0.2
    soc_max = int(soc_range.group(2))/100 if soc_range else 0.9

    # -----------------------------
    # 3) SMR 파라미터
    # -----------------------------
    smr_cap = parse_number(re.search(r"정격\s*(\d+)\s*MW", scenario).group()) if "SMR" in scenario else 5
    smr_min = parse_number(re.search(r"최소\s*(\d+)\s*MW", scenario).group()) if "최소" in scenario else 3
    smr_ramp = parse_number(re.search(r"ramp\s*(\d+)\s*MW", scenario).group()) if "ramp" in scenario else 1

    # -----------------------------
    # 4) PV 예측 (간단 자동 생성)
    # -----------------------------
    pv_max = parse_number(re.search(r"PV\s*최대\s*(\d+)\s*MW", scenario).group()) if "PV" in scenario else 4
    pv_profile = [min(pv_max, max(0, 4 - abs(t-12))) for t in range(24)]

    # -----------------------------
    # 5) Grid 가격 (피크 시간에 상승)
    # -----------------------------
    grid_price = [80]*24
    for t in [20, 21, 22]:
        grid_price[t] = 150

    # -----------------------------
    # 6) extracted_params 채우기
    # -----------------------------
    params = {
        "time_horizon": 24,
        "demand_profile": load_profile,
        "pv_profile": pv_profile,
        "ess_capacity_mwh": ess_cap,
        "ess_p_charge_max": ess_p,
        "ess_p_discharge_max": ess_p,
        "ess_soc_min": soc_min,
        "ess_soc_max": soc_max,
        "ess_soc_init": 0.5,
        "smr_capacity_mw": smr_cap,
        "smr_min_output_mw": smr_min,
        "smr_ramp_limit": smr_ramp,
        "grid_price": grid_price
    }

    state.extracted_params = params

    # -----------------------------
    # 7) state의 numerical 값도 자동 초기화
    # -----------------------------
    state.time = 0
    state.datacenter_load = load_profile[0]
    state.grid_price = grid_price[0]
    state.solar_gen = pv_profile[0]
    state.ess_soc = 0.5
    state.mgt_output = smr_min

    state.constraint_values = {
        "ess_capacity": ess_cap,
        "ess_max_charge": ess_p,
        "ess_max_discharge": ess_p,
        "ess_soc_min": soc_min,
        "ess_soc_max": soc_max,

        "smr_min": smr_min,
        "smr_max": smr_cap,
        "smr_ramp": smr_ramp,
    }

    state.logs.append("DataExtractorAgent: parsed numerical scenario.")

    return state
