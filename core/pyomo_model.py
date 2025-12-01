# core/pyomo_model.py

from pyomo.environ import ConcreteModel, Var, Objective, Constraint, NonNegativeReals, minimize

def build_two_gen_model(params):
    m = ConcreteModel()

    g1, g2 = params.generators["G1"], params.generators["G2"]
    D = params.demand

    # Variables
    m.P1 = Var(domain=NonNegativeReals, bounds=(g1.p_min, g1.p_max))
    m.P2 = Var(domain=NonNegativeReals, bounds=(g2.p_min, g2.p_max))

    # Power balance
    m.balance = Constraint(expr=m.P1 + m.P2 == D)

    # Cost objective
    m.obj = Objective(
        expr= g1.a*m.P1**2 + g1.b*m.P1 + g1.c
            + g2.a*m.P2**2 + g2.b*m.P2 + g2.c,
        sense=minimize
    )
    return m
