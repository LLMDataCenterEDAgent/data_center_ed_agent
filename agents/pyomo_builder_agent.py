# agents/pyomo_builder_agent.py

from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective, NonNegativeReals,
    RangeSet, SolverFactory, minimize
)
from core.state import EDAgentState


def pyomo_builder_node(state: EDAgentState) -> EDAgentState:
    params = state.extracted_params

    model = ConcreteModel()
    T = params["time_horizon"]
    model.T = RangeSet(0, T-1)
    model.params = params

    model.soc = Var(model.T, domain=NonNegativeReals)
    model.grid = Var(model.T, domain=NonNegativeReals)
    model.charge = Var(model.T, domain=NonNegativeReals)
    model.discharge = Var(model.T, domain=NonNegativeReals)
    model.smr = Var(model.T, domain=NonNegativeReals)

    # Initial SOC
    model.soc[0].fix(params["ess_soc_init"])

    # SOC update rule
    def soc_update_rule(m, t):
        if t == 0:
            return Constraint.Skip
        return (
            m.soc[t] ==
            m.soc[t-1] + m.charge[t] - m.discharge[t]
        )
    model.soc_update = Constraint(model.T, rule=soc_update_rule)

    # SOC bounds
    model.soc_min = Constraint(model.T, rule=lambda m, t: m.soc[t] >= m.params["ess_soc_min"])
    model.soc_max = Constraint(model.T, rule=lambda m, t: m.soc[t] <= m.params["ess_soc_max"])

    # Power balance
    model.balance = Constraint(
        model.T,
        rule=lambda m, t: m.grid[t] + m.smr[t] + m.params["pv_profile"][t]
                          + m.discharge[t] - m.charge[t]
                          == m.params["demand_profile"][t]
    )

    # Objective
    model.obj = Objective(
        rule=lambda m: sum(
            m.grid[t] * m.params["grid_price"][t] for t in m.T
        ),
        sense=minimize
    )

    # store model
    state.model_code = model
    state.logs.append("Pyomo template model built.")
    return state
