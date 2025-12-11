# core/pyomo_model.py

import pyomo.environ as pyo

class PyomoModelBuilder:
    """
    LLM(Parsing Agent)이 넘겨준 데이터를 기반으로
    Pyomo 최적화 모델을 동적으로 생성하는 빌더 클래스
    """

    def create_time_series_model(self, parsed_data):
        """
        Args:
            parsed_data (dict): 시계열 데이터 및 컴포넌트 설정 정보
            예: {
                'time_steps': 96,
                'demand': [100, 110, ...],
                'components': {
                    'grid': {'price_schedule': [...]},
                    'mgt': {'ramp_rate': 10, ...},
                    'ess': {'capacity': 500, 'efficiency': 0.95, ...}
                }
            }
        """
        # 1. 모델 초기화
        model = pyo.ConcreteModel()
        
        # 시간축 설정 (0 ~ T-1)
        # parsed_data에 time_steps 정보가 없으면 demand 리스트 길이로 추론
        T = parsed_data.get('time_steps', len(parsed_data['demand']))
        model.T = pyo.RangeSet(0, T - 1)

        # 목적함수와 공급항 리스트 초기화
        # obj_terms: 비용 항들을 모음 (sum(obj_terms))
        # supply_terms: 전력 공급원 변수들을 모음 (grid + mgt + pv + discharge - charge ...)
        model.obj_terms = []
        model.supply_terms = []

        components = parsed_data.get('components', {})

        # =================================================================
        # 2. Grid (전력망) - 정보가 있으면 생성
        # =================================================================
        if 'grid' in components:
            # 변수: 시간대별 그리드 전력 사용량 (0 이상)
            model.P_grid = pyo.Var(model.T, domain=pyo.NonNegativeReals)
            
            # (옵션) 최대 수전 용량 제약
            if 'limit' in components['grid']:
                limit = components['grid']['limit']
                model.Constraint_Grid_Limit = pyo.Constraint(
                    model.T, rule=lambda m, t: m.P_grid[t] <= limit
                )

            # 비용 항 추가: P_grid[t] * 전력단가[t]
            def grid_cost_rule(m, t):
                # 가격 정보가 리스트(시계열)인지 단일 값인지 확인
                prices = components['grid']['price_schedule']
                price = prices[t] if isinstance(prices, list) else prices
                return m.P_grid[t] * price
            
            model.obj_terms.append(grid_cost_rule)
            model.supply_terms.append(model.P_grid)

        # =================================================================
        # 3. MGT (마이크로 가스터빈) - 정보가 있으면 생성
        # =================================================================
        if 'mgt' in components:
            model.P_mgt = pyo.Var(model.T, domain=pyo.NonNegativeReals)

            # 용량 제약 (Min/Max)
            p_min = components['mgt'].get('min', 0)
            p_max = components['mgt'].get('max', 10000) # 기본값 크게
            
            def mgt_capacity_rule(m, t):
                return (p_min, m.P_mgt[t], p_max)
            model.Constraint_MGT_Capacity = pyo.Constraint(model.T, rule=mgt_capacity_rule)

            # [MGT] Ramp Rate 제약 (수정된 부분)
            if 'ramp_rate' in components['mgt']:
                ramp_limit = components['mgt']['ramp_rate']
                
                def ramp_rule(m, t):
                    if t == 0: return pyo.Constraint.Skip
                    # [수정] 파이썬의 a <= x <= b 문법 대신 pyo.inequality(a, x, b) 사용
                    return pyo.inequality(-ramp_limit, m.P_mgt[t] - m.P_mgt[t-1], ramp_limit)
                
                model.Constraint_MGT_Ramp = pyo.Constraint(model.T, rule=ramp_rule)

            # 비용 항 추가 (연료비 등): a*P^2 + b*P + c 형태 혹은 단순 단가
            # 여기선 단순화를 위해 선형 비용(marginal cost) 가정
            if 'cost_coeff' in components['mgt']:
                cost = components['mgt']['cost_coeff']
                model.obj_terms.append(lambda m, t: m.P_mgt[t] * cost)
            
            model.supply_terms.append(model.P_mgt)

        # =================================================================
        # 4. PV (태양광) - 정보가 있으면 생성
        # =================================================================
        if 'pv' in components:
            # PV는 보통 제어 불가능하므로 변수가 아니라 파라미터로 처리하거나
            # Curtailment(출력 제한)를 고려해 변수로 둘 수 있음. 여기선 Curtailment 가능하게 변수로 설정.
            model.P_pv = pyo.Var(model.T, domain=pyo.NonNegativeReals)
            
            # 제약: 실제 발전량 <= 예측량 (Forecast)
            forecast = components['pv']['forecast']
            def pv_limit_rule(m, t):
                val = forecast[t] if isinstance(forecast, list) else forecast
                return m.P_pv[t] <= val
            model.Constraint_PV_Limit = pyo.Constraint(model.T, rule=pv_limit_rule)
            
            # 태양광은 운영비 0원 (또는 유지보수비)
            model.supply_terms.append(model.P_pv)

        # =================================================================
        # 5. ESS (에너지 저장장치) - 정보가 있으면 생성
        # =================================================================
        if 'ess' in components:
            # 충전, 방전, SOC 변수
            model.P_charge = pyo.Var(model.T, domain=pyo.NonNegativeReals)
            model.P_discharge = pyo.Var(model.T, domain=pyo.NonNegativeReals)
            
            # ESS 용량
            capacity = components['ess'].get('capacity', 1000)
            model.SOC = pyo.Var(model.T, bounds=(0, capacity)) # kWh 단위

            eff = components['ess'].get('efficiency', 0.95) # 효율
            initial_soc = components['ess'].get('initial_soc', capacity * 0.5)

            # SOC Dynamics (시간 연결 제약)
            # SOC[t] = SOC[t-1] + (Charge * eff) - (Discharge / eff)
            # 1시간 간격 가정 (dt=1), 만약 15분이면 dt=0.25 곱해야 함
            dt = 1.0 
            
            def soc_rule(m, t):
                prev_soc = m.SOC[t-1] if t > 0 else initial_soc
                return m.SOC[t] == prev_soc + (m.P_charge[t] * eff - m.P_discharge[t] / eff) * dt
            model.Constraint_SOC_Dynamics = pyo.Constraint(model.T, rule=soc_rule)
            
            # 공급항: (방전 - 충전)
            # 수급 밸런스 식에서 '공급'으로 작용
            def ess_supply_expression(m, t):
                return m.P_discharge[t] - m.P_charge[t]
            
            # Pyomo Expression 객체로 만들어서 리스트에 추가
            model.Expr_ESS_Net = pyo.Expression(model.T, rule=ess_supply_expression)
            model.supply_terms.append(model.Expr_ESS_Net)
            
            # (옵션) ESS 열화 비용(Degradation Cost) 추가 가능

        # =================================================================
        # 6. 수급 밸런스 (Power Balance) - 필수
        # =================================================================
        def power_balance_rule(m, t):
            # 모든 공급원 합 (Grid + MGT + PV + ESS_Discharge - ESS_Charge)
            total_supply = sum(term[t] for term in model.supply_terms)
            
            # 수요 (Demand)
            demand_val = parsed_data['demand'][t]
            
            # (옵션) 데이터센터 워크로드 이동(Shifting) 기능이 있다면 수요가 변수가 됨
            # 여기선 고정 수요로 가정
            return total_supply == demand_val
            
        model.Constraint_PowerBalance = pyo.Constraint(model.T, rule=power_balance_rule)

        # =================================================================
        # 7. 목적함수 (Objective)
        # =================================================================
        def objective_rule(m):
            # 모든 시간대(T)의 비용 합산 (Global Optimization)
            return sum(term(m, t) for term in model.obj_terms for t in m.T)
        
        model.Objective = pyo.Objective(rule=objective_rule, sense=pyo.minimize)

        return model