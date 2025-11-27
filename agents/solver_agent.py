# agents/solver_agent.py

import traceback
from core.state import EDAgentState


def solver_agent_node(state: EDAgentState) -> EDAgentState:
    local_ns = {}

    try:
        code_to_run = "params = " + repr(state.extracted_params) + "\n\n" + state.model_code
        exec(code_to_run, {}, local_ns)

        solution = local_ns.get("solution_summary", "No summary generated.")
        state.solution_summary = str(solution)

        if "error" in state.solution_summary.lower() or "infeasible" in state.solution_summary.lower():
            state.constraint_violation = True
            state.logs.append("SolverAgent: infeasible → back to constraint.")
        else:
            state.constraint_violation = False
            state.logs.append("SolverAgent: feasible solution found.")

    except Exception:
        state.solution_summary = traceback.format_exc()
        state.constraint_violation = True
        state.logs.append("SolverAgent: EXCEPTION → back to constraint.")

    return state
