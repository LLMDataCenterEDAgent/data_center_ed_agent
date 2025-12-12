# core/pyomo_model.py

import pyomo.environ as pyo

class PyomoModelBuilder:
    def create_time_series_model(self, params):
        """
        params: EDParams 객체 (Pydantic)
        """
        model = pyo.ConcreteModel()
        
        # 1. 시간축 설정
        # demand_profile이 있으면 그 길이를 사용, 없으면 time_steps 사용
        if params.demand_profile:
            T = len(params.demand_profile)
        else:
            T = params.time_steps
            
        model.T = pyo.RangeSet(0, T - 1)
        
        model.obj_terms = []
        model.supply_terms = []

        # =================================================================
        # 2. 발전기 (MGT/G1/G2)
        # =================================================================
        if params.generators:
            for name, gen in params.generators.items():
                # 변수 생성: P_gen[name, t]
                p_var = pyo.Var(model.T, domain=pyo.NonNegativeReals, bounds=(gen.p_min, gen.p_max))
                model.add_component(f"P_{name}", p_var)
                
                # 공급항 추가
                model.supply_terms.append(p_var)
                
                # 비용항 추가 (a*P^2 + b*P + c)
                def gen_cost_rule(m, t):
                    p = p_var[t]
                    return gen.a * p**2 + gen.b * p + gen.c
                
                # 단순 선형 비용(cost_coeff)만 있는 경우 처리
                if gen.cost_coeff is not None and gen.a == 0 and gen.b == 0:
                     def gen_cost_rule_linear(m, t):
                        return p_var[t] * gen.cost_coeff
                     model.obj_terms.append(gen_cost_rule_linear)
                else:
                    model.obj_terms.append(gen_cost_rule)

                # Ramp Rate 제약
                if gen.ramp_rate:
                    def ramp_rule(m, t):
                        if t == 0: return pyo.Constraint.Skip
                        return pyo.inequality(-gen.ramp_rate, p_var[t] - p_var[t-1], gen.ramp_rate)
                    model.add_component(f"Ramp_{name}", pyo.Constraint(model.T, rule=ramp_rule))

        # =================================================================
        # 3. ESS (배터리)
        # =================================================================
        if params.ess:
            for name, ess in params.ess.items():
                # 변수
                p_chg = pyo.Var(model.T, domain=pyo.NonNegativeReals, bounds=(0, ess.max_power_mw))
                p_dis = pyo.Var(model.T, domain=pyo.NonNegativeReals, bounds=(0, ess.max_power_mw))
                soc = pyo.Var(model.T, bounds=(ess.min_soc * ess.capacity_mwh, ess.max_soc * ess.capacity_mwh))
                
                model.add_component(f"P_chg_{name}", p_chg)
                model.add_component(f"P_dis_{name}", p_dis)
                model.add_component(f"SOC_{name}", soc)
                
                # 공급항: 방전 - 충전
                model.supply_terms.append(p_dis)
                def charge_neg_rule(m, t): return -p_chg[t]
                # *주의: 리스트에 함수를 넣는 구조가 아니라면 Expression 사용 권장
                # 여기선 단순화를 위해 supply_terms 처리를 나중에 sum 할 때 고려
                
                # SOC Dynamics: SOC[t] = SOC[t-1] + (Charge*eff - Discharge/eff) * dt
                dt = 0.25 # 15분 간격 = 0.25시간
                def soc_rule(m, t):
                    prev = soc[t-1] if t > 0 else ess.initial_soc * ess.capacity_mwh
                    return soc[t] == prev + (p_chg[t] * ess.efficiency - p_dis[t] / ess.efficiency) * dt
                model.add_component(f"SOC_Rule_{name}", pyo.Constraint(model.T, rule=soc_rule))
                
                # 열화 비용 (Aging Cost) -> 방전량에 비례한다고 가정
                if ess.aging_cost > 0:
                    model.obj_terms.append(lambda m, t: p_dis[t] * ess.aging_cost)

        # =================================================================
        # 4. Grid (수전) - Demand Profile과 Net Load 개념 적용
        # =================================================================
        # Grid는 항상 존재한다고 가정 (혹은 params에 명시)
        # 여기서는 부족분을 Grid가 채우는 구조
        model.P_grid = pyo.Var(model.T, domain=pyo.NonNegativeReals)
        model.supply_terms.append(model.P_grid)
        
        # Grid 가격 (단순화: 시간대별 가격이 params에 없으면 고정값 가정, 실제론 추가 필요)
        # 사용자가 제공한 코드엔 price_schedule이 main.py에 있었음.
        # EDParams에 grid_price_profile 필드를 추가하는 것이 좋음. 
        # 임시로: 낮(40~72구간) 150원, 나머지 60원
        def grid_cost(m, t):
            price = 150 if 36 <= t <= 72 else 60
            return m.P_grid[t] * price
        model.obj_terms.append(grid_cost)

        # =================================================================
        # 5. 수급 밸런스
        # =================================================================
        def balance_rule(m, t):
            # 공급 합 (발전기 + Grid + ESS방전)
            supply = sum(comp[t] for comp in model.supply_terms if isinstance(comp, pyo.Var))
            
            # ESS 충전은 수요처럼 뺌 (위에서 supply_terms에 안 넣었으므로 여기서 처리)
            if params.ess:
                for name in params.ess:
                    p_chg = getattr(m, f"P_chg_{name}")
                    supply -= p_chg[t]
            
            # 수요 (Net Load)
            demand = params.demand_profile[t]
            
            return supply == demand
            
        model.Balance = pyo.Constraint(model.T, rule=balance_rule)

        # Objective
        model.Obj = pyo.Objective(expr=sum(term(model, t) for term in model.obj_terms for t in model.T), sense=pyo.minimize)
        
        return model