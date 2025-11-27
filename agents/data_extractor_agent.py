# agents/data_extractor_agent.py

import json
from core.llm import call_llm
from core.state import EDAgentState

def clean_json_text(text: str) -> str:
    """Remove codeblock fences like ```json or ```"""
    text = text.strip()
    if text.startswith("```"):
        # remove ```json or ``` 
        text = text.split("```", 1)[1]  
        text = text.strip()
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
        text = text.strip()
    return text

def data_extractor_node(state: EDAgentState) -> EDAgentState:
    system_prompt = """
    You MUST return a pure JSON dictionary with NO markdown, NO code block, 
    NO ```json``` wrapper. Only raw JSON. No explanations.

    Required keys:
      - time_horizon
      - demand_profile
      - pv_profile
      - ess_capacity_mwh
      - ess_p_charge_max
      - ess_p_discharge_max
      - ess_soc_min
      - ess_soc_max
      - smr_capacity_mw
      - smr_min_output_mw
      - smr_ramp_limit
      - grid_price
    """
    user_prompt = f"Scenario:\n{state.scenario}"

    raw = call_llm(system_prompt, user_prompt)

    cleaned = clean_json_text(raw)

    try:
        params = json.loads(cleaned)
    except:
        params = eval(cleaned)  # fallback
    
    state.extracted_params = params
    state.logs.append("DataExtractorAgent: parameters extracted.")
    return state
