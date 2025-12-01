# agents/solver_agent.py

from core.solver_interface import solve_with_pyomo
from core.analytic_solver import analytic_solve_two_gen

def solve_ed(params, method="analytic"):
    if method == "analytic":
        return analytic_solve_two_gen(params)
    else:
        model = build_two_gen_model(params)
        return solve_with_pyomo(model)
