# core/dynamic_solver.py

import pyomo.environ as pyo
from state.schemas import EDParams, EDSolution

def solve_dynamic_ed(params: EDParams) -> EDSolution:
    m = pyo.ConcreteModel()
    T_len = params.time_steps
    m.T = pyo.RangeSet(0, T_len - 1)
    
    gen_names = list(params.generators.keys())
    m.P_gen = pyo.Var(gen_names, m.T, domain=pyo.NonNegativeReals)
    
    ess_names = list(params.ess.keys()) if params.ess else []
    if ess_names:
        m.P_chg = pyo.Var(ess_names, m.T, domain=pyo.NonNegativeReals)
        m.P_dis = pyo.Var(ess_names, m.T, domain=pyo.NonNegativeReals)
        m.SOC = pyo.Var(ess_names, m.T, domain=pyo.NonNegativeReals)

    m.P_grid_import = pyo.Var(m.T, domain=pyo.NonNegativeReals) 
    m.P_grid_export = pyo.Var(m.T, domain=pyo.NonNegativeReals)

    # Constraints
    def balance_rule(model, t):
        supply = model.P_grid_import[t] + sum(model.P_gen[g, t] for g in gen_names)
        if ess_names: supply += sum(model.P_dis[e, t] for e in ess_names)
        demand = params.demand_profile[t] + model.P_grid_export[t]
        if ess_names: demand += sum(model.P_chg[e, t] for e in ess_names)
        return supply == demand
    m.Balance = pyo.Constraint(m.T, rule=balance_rule)

    def gen_bounds_rule(model, g, t):
        spec = params.generators[g]
        return (spec.p_min, model.P_gen[g, t], spec.p_max)
    m.GenBounds = pyo.Constraint(gen_names, m.T, rule=gen_bounds_rule)
    
    def ramp_rule(model, g, t):
        if t == 0: return pyo.Constraint.Skip
        spec = params.generators[g]
        return (-spec.ramp_rate, model.P_gen[g, t] - model.P_gen[g, t-1], spec.ramp_rate)
    m.Ramp = pyo.Constraint(gen_names, m.T, rule=ramp_rule)
    
    if ess_names:
        dt = 0.25
        def soc_rule(model, e, t):
            spec = params.ess[e]
            prev = model.SOC[e, t-1] if t > 0 else spec.initial_soc * spec.capacity_mwh
            return model.SOC[e, t] == prev + (model.P_chg[e, t]*spec.efficiency - model.P_dis[e, t]/spec.efficiency) * dt
        m.SOC_Dyn = pyo.Constraint(ess_names, m.T, rule=soc_rule)
        
        def soc_limit(model, e, t):
            spec = params.ess[e]
            return (spec.min_soc * spec.capacity_mwh, model.SOC[e, t], spec.max_soc * spec.capacity_mwh)
        m.SOC_Limit = pyo.Constraint(ess_names, m.T, rule=soc_limit)
        
        def ess_power_limit(model, e, t):
            return model.P_chg[e, t] + model.P_dis[e, t] <= params.ess[e].max_power_mw
        m.ESS_Power = pyo.Constraint(ess_names, m.T, rule=ess_power_limit)

    # [핵심] Objective Function: 변동비 + 고정비(base_rate)
    def obj_rule(model):
        variable_cost = 0
        for t in model.T:
            # 1. 발전 비용
            for g in gen_names:
                spec = params.generators[g]
                p = model.P_gen[g, t]
                if spec.a != 0 or spec.b != 0:
                    variable_cost += spec.a * p**2 + spec.b * p + spec.c
                elif spec.cost_coeff:
                    variable_cost += p * spec.cost_coeff
            
            # 2. 전력망 구입 비용
            grid_price = params.grid_price_profile[t] if params.grid_price_profile else 200000.0
            variable_cost += model.P_grid_import[t] * grid_price
            
            # 3. ESS 노화 비용
            if ess_names:
                for e in ess_names:
                    variable_cost += model.P_dis[e, t] * params.ess[e].aging_cost
        
        # [여기서 더함!] 기본요금 합산
        total_cost = variable_cost + (params.base_rate if hasattr(params, 'base_rate') else 0.0)
        return total_cost
    
    m.Obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)
    
    solver = pyo.SolverFactory('gurobi')
    res = solver.solve(m, tee=True)
    
    sol = EDSolution()
    sol.cost = pyo.value(m.Obj)
    sol.schedule = {}
    sol.schedule['P_grid'] = [pyo.value(m.P_grid_import[t]) - pyo.value(m.P_grid_export[t]) for t in m.T]
    
    for g in gen_names:
        sol.schedule[f'P_{g}'] = [pyo.value(m.P_gen[g, t]) for t in m.T]
        
    if ess_names:
        sol.ess_schedule = {}
        for e in ess_names:
            sol.ess_schedule[e] = {
                'charge': [pyo.value(m.P_chg[e, t]) for t in m.T],
                'discharge': [pyo.value(m.P_dis[e, t]) for t in m.T],
                'soc': [pyo.value(m.SOC[e, t]) for t in m.T]
            }
            
    return sol