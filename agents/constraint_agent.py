# agents/constraint_agent.py

import json
from core.llm import call_llm
from core.state import EDAgentState


def constraint_agent_node(state: EDAgentState) -> EDAgentState:
    system_prompt = """
    You are a power system optimization expert.
    Generate ED constraints in LaTeX-like equations + explanation.
    Include:
     - Power balance
     - ESS SOC update + bounds
     - Charge/discharge limits
     - SMR min/max + ramp
     - PV bounds
    """
    user_prompt = json.dumps(state.extracted_params, indent=2, ensure_ascii=False)

    constraints_text = call_llm(system_prompt, user_prompt, model="gpt-4.1-mini")
    state.constraints = constraints_text
    state.constraint_violation = False
    state.logs.append("ConstraintAgent: constraints generated.")
    return state
