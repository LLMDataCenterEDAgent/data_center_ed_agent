# agents/formulation_agent.py

from core.llm import call_llm
from core.state import EDAgentState


def formulation_agent_node(state: EDAgentState) -> EDAgentState:

    system_prompt = """
    You are a Python & Pyomo expert.
    Generate a COMPLETE Pyomo model script.

    IMPORTANT RULES:
    - ONLY return pure Python code (NO markdown, NO backticks).
    - Code MUST be executable by exec().
    - A dict called 'params' already exists.
    - At the top of the code, import all required Pyomo classes:
        from pyomo.environ import (
            ConcreteModel, Var, Constraint, Objective, NonNegativeReals,
            RangeSet, SolverFactory
        )

    PARAMETER ACCESS RULES:
    - At the top, assign: model.params = params
    - Inside ANY rule, NEVER access params directly.
    - ALWAYS use m.params["key"] rather than params["key"].
    - NEVER create standalone variable names such as soc_init, ess_soc_init, soc0, initial_soc, etc.
    - The ONLY valid way to access initial SOC is: m.params["ess_soc_init"]


    MODEL REQUIREMENTS:
    - model = ConcreteModel()
    - model.T = RangeSet(params["time_horizon"])
    - Define variables: soc[t], grid_use[t], ess_charge[t], ess_discharge[t], smr_output[t]
    - Define constraints:
        * power_balance
        * soc_update
        * soc_bounds
        * charge/discharge limits
        * smr min/max
        * smr ramp limit
    - If constraint should skip first t, use: return Constraint.Skip
    - ALWAYS refer to Constraint.Skip (not model.Constraint.Skip)

    OBJECTIVE:
    - minimize sum(grid_use[t] * m.params["grid_price"][t])

    OUTPUT:
    - After solving, write a string to variable: solution_summary

    ONLY output runnable Python code.
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
