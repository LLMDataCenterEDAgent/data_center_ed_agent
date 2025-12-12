# core/dynamic_solver.py

import pyomo.environ as pyo
from state.schemas import EDParams, EDSolution

def solve_dynamic_ed(params: EDParams) -> EDSolution:
    m = pyo.ConcreteModel()
    T_len = params.time_steps
    m.T = pyo.RangeSet(0, T_len - 1)
    
    # --- Variables ---
    # 1. Generators
    gen_names = list(params.generators.keys())
    m.P_gen = pyo.Var(gen_names, m.T, domain=pyo.NonNegativeReals)
    
    # 2. ESS
    ess_names = list(params.ess.keys()) if params.ess else []
    if ess_names:
        m.P_chg = pyo.Var(ess_names, m.T, domain=pyo.NonNegativeReals)
        m.P_dis = pyo.Var(ess_names, m.T, domain=pyo.NonNegativeReals)
        m.SOC = pyo.Var(ess_names, m.T, domain=pyo.NonNegativeReals)

    # 3. Grid (Slack Variable)
    # 발전기가 최소 출력 때문에 수요보다 전기를 많이 만들면 -> Grid로 내다 팜(Export)
    # 발전기가 모자라면 -> Grid에서 사옴(Import)
    # 이를 위해 Grid 변수를 '자유 변수(Reals)'로 두거나 Import/Export 분리
    m.P_grid_import = pyo.Var(m.T, domain=pyo.NonNegativeReals) 
    m.P_grid_export = pyo.Var(m.T, domain=pyo.NonNegativeReals)

    # --- Constraints ---
    
    # (1) Power Balance: Supply == Demand
    def balance_rule(model, t):
        # 공급원: 발전기 + ESS방전 + Grid수입
        supply = model.P_grid_import[t] + sum(model.P_gen[g, t] for g in gen_names)
        if ess_names:
            supply += sum(model.P_dis[e, t] for e in ess_names)
            
        # 수요처: 순부하 + ESS충전 + Grid수출
        demand = params.demand_profile[t] + model.P_grid_export[t]
        if ess_names:
            demand += sum(model.P_chg[e, t] for e in ess_names)
            
        return supply == demand
    m.Balance = pyo.Constraint(m.T, rule=balance_rule)

    # (2) Generator Limits (P_min <= P <= P_max)
    def gen_bounds_rule(model, g, t):
        spec = params.generators[g]
        return (spec.p_min, model.P_gen[g, t], spec.p_max)
    m.GenBounds = pyo.Constraint(gen_names, m.T, rule=gen_bounds_rule)
    
    # (3) ESS Constraints
    if ess_names:
        dt = 0.25 # 15min
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

    # --- Objective: Minimize Cost ---
    def obj_rule(model):
        total_cost = 0
        for t in model.T:
            # 1. Generator Cost (Quadratic: a*P^2 + b*P + c)
            for g in gen_names:
                spec = params.generators[g]
                p = model.P_gen[g, t]
                # 2차 비용 함수 적용
                if spec.a != 0 or spec.b != 0:
                    total_cost += spec.a * p**2 + spec.b * p + spec.c
                elif spec.cost_coeff:
                    total_cost += p * spec.cost_coeff
                
            # 2. Grid Cost (Import는 비용, Export는 수익 혹은 0원)
            # 여기선 Feasibility 확보가 목적이므로 Import 비용을 비싸게(1000) 책정해
            # 가급적 발전기를 우선 쓰도록 유도
            total_cost += model.P_grid_import[t] * 1000 
            # Export는 버리는 전력(Dump)으로 칠 수도 있고 수익으로 칠 수도 있음. 일단 0원 처리.
            
            # 3. ESS Aging Cost
            if ess_names:
                for e in ess_names:
                    total_cost += model.P_dis[e, t] * params.ess[e].aging_cost
                    
        return total_cost
    
    m.Obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)
    
    # Solve
    solver = pyo.SolverFactory('gurobi')
    res = solver.solve(m, tee=True)
    
    # Result Packing
    sol = EDSolution()
    sol.cost = pyo.value(m.Obj)
    sol.note = str(res.solver.termination_condition)
    
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