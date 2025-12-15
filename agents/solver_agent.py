# agents/solver_agent.py

from state.base_state import AgentState
from core.dynamic_solver import solve_dynamic_ed

class SolverAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Solver Agent Started ---")
        
        params = state.get("params")
        if not params:
            print("Error: No params found.")
            return state

        try:
            print(f">>> Solving Dynamic ED (Pyomo) for {len(params.generators)} gens...")
            sol = solve_dynamic_ed(params)
            
            # 원본 객체 저장
            state["solution"] = sol
            
            # 결과 변환 (Dict) - main.py나 ExplanationAgent가 쓰기 편하게
            output_dict = {}
            output_dict['Total_Cost'] = sol.cost
            
            # [핵심] 동적 키 생성 (어떤 발전기 이름이든 다 담기)
            gen_names = list(params.generators.keys())
            ess_names = list(params.ess.keys()) if params.ess else []

            for t in range(params.time_steps):
                row = {}
                
                # 1. Grid
                if 'P_grid' in sol.schedule:
                    row['P_grid'] = sol.schedule['P_grid'][t]
                
                # 2. 발전기들 (GT1, SMR1 등 동적 처리)
                for g in gen_names:
                    # solve_dynamic_ed 결과에서 해당 발전기 이름 찾기
                    # core/dynamic_solver.py가 P_{name} 형태로 저장한다고 가정
                    key = f'P_{g}'
                    if key in sol.schedule:
                        row[key] = sol.schedule[key][t]
                    else:
                        row[key] = 0.0 # 없으면 0
                
                # 3. ESS들 (ESS1, ESS2 등 동적 처리)
                if sol.ess_schedule:
                    for e in ess_names:
                        if e in sol.ess_schedule:
                            row[f'P_dis_{e}'] = sol.ess_schedule[e]['discharge'][t]
                            row[f'P_chg_{e}'] = sol.ess_schedule[e]['charge'][t]
                            row[f'SOC_{e}'] = sol.ess_schedule[e]['soc'][t]
                
                # 4. PV (시각화용)
                if params.pv_profile:
                    row['P_PV'] = params.pv_profile[t]
                else:
                    row['P_PV'] = 0.0
                
                output_dict[t] = row
            
            state["solution_output"] = output_dict
            
            print(f"Optimization completed. Cost: {sol.cost:,.0f}")
            print(f"✅ Results packed for: {gen_names} + {ess_names}")

        except Exception as e:
            print(f"Solver Error: {e}")
            import traceback
            traceback.print_exc()
            state["solution"] = None

        return state