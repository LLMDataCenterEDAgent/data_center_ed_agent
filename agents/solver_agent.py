# agents/solver_agent.py
from pyomo.environ import SolverFactory

def solver_node(state):

    model = state["model"]
    solver = SolverFactory("gurobi")

    solver.solve(model, tee=False)

    solution = {
        "P_grid": [model.P_grid[t]() for t in model.T],
        "P_pv":   [model.P_pv[t]() for t in model.T],
        "P_mgt":  [model.P_mgt[t]() for t in model.T],
        "P_smr":  [model.P_smr[t]() for t in model.T],
        "SOC":    [model.SOC[t]() for t in model.T],
        "OBJ":    model.OBJ()
    }

    state["solution"] = solution
    return state