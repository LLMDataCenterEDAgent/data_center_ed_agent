# agents/formulation_agent.py

from core.llm import call_llm
from core.state import EDAgentState


def formulation_agent_node(state: EDAgentState) -> EDAgentState:
    system_prompt = """
    You are a Python & Pyomo expert. Generate a FULL Pyomo model script.

    Requirements:
    - params dict already exists
    - build ConcreteModel()
    - define sets/vars
    - apply constraints from description
    - objective: minimize grid cost
    - use SolverFactory("glpk")
    - after solving, produce `solution_summary` string
    - return ONLY runnable Python code
    """
    user_prompt = f"""
    Parameters:
    {state.extracted_params}

    Constraints:
    {state.constraints}
    """

    model_code = call_llm(system_prompt, user_prompt, model="gpt-4.1-mini")
    state.model_code = model_code
    state.logs.append("FormulationAgent: Pyomo code generated.")
    return state
