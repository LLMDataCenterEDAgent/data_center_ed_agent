# agents/scenario_llm_agent.py

from core.llm import call_llm
from core.state import EDAgentState

def scenario_llm_node(state: EDAgentState) -> EDAgentState:
    """
    자연어 기반 시나리오를 더 정해진 형태의 문장으로 정규화(normalize)하여
    DataExtractorAgent가 문자열 파싱하기 쉽게 만드는 LLM 에이전트.
    """

    system_prompt = """
    You are an energy systems scenario rewriter.
    Your job is to rewrite a messy natural-language scenario into a clear,
    structured description using consistent numeric expressions.

    RULES:
    - Always convert MW, MWh, %, hour ranges into explicit numeric forms.
    - Use explicit time ranges like "20~22시".
    - Use the keywords: demand_profile, ESS, SMR, PV, Grid.
    - Keep the meaning the same, but rewrite it more formally.
    - DO NOT invent parameters that were not in the original.
    - DO NOT create JSON. Only plain text.
    """

    user_prompt = f"Rewrite the following scenario:\n\n{state.scenario}"

    rewritten = call_llm(system_prompt, user_prompt)
    state.scenario = rewritten
    state.logs.append("ScenarioLLM: scenario normalized.")

    return state
