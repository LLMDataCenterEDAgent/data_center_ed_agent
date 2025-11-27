from core.llm import call_llm
from core.state import EDAgentState

def solution_explain_node(state: EDAgentState) -> EDAgentState:
    system_prompt = "You are an energy expert. Explain the optimal ED dispatch in simple words."
    user_prompt = f"""
    Solution:
    {state.solution_summary}
    """

    explanation = call_llm(system_prompt, user_prompt)

    state.solution_explanation = explanation
    state.logs.append("Solution explain generated.")
    return state
