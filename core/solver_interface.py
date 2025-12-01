# core/solver_interface.py

from pyomo.opt import SolverFactory
from state.schemas import EDSolution

def solve_with_pyomo(model, use_gurobi=True):
    solver = SolverFactory("gurobi" if use_gurobi else "cbc")
    result = solver.solve(model, tee=False)

    P1 = float(model.P1.value)
    P2 = float(model.P2.value)
    cost = float(model.obj())

    return EDSolution(
        Pg={"G1": P1, "G2": P2},
        cost=cost,
        note=str(result.solver.termination_condition)
    )
