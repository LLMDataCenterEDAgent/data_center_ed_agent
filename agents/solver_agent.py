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
            print(">>> Solving Dynamic ED (Pyomo)...")
            sol = solve_dynamic_ed(params)
            
            # 원본 객체 저장
            state["solution"] = sol
            
            # 결과 변환 (Dict)
            output_dict = {}
            output_dict['Total_Cost'] = sol.cost
            
            # 스케줄 데이터 변환
            for t in range(params.time_steps):
                row = {}
                
                # 1. Grid
                if 'P_grid' in sol.schedule:
                    row['P_grid'] = sol.schedule['P_grid'][t]
                
                # 2. Generators (G1, G2 등)
                for key in sol.schedule:
                    if key.startswith('P_') and key != 'P_grid':
                        row[key] = sol.schedule[key][t]
                
                # 3. ESS
                if sol.ess_schedule:
                    for ess_name in sol.ess_schedule:
                        row[f'P_dis_{ess_name}'] = sol.ess_schedule[ess_name]['discharge'][t]
                        row[f'P_chg_{ess_name}'] = sol.ess_schedule[ess_name]['charge'][t]
                        row[f'SOC_{ess_name}'] = sol.ess_schedule[ess_name]['soc'][t]
                
                # 4. [핵심 추가] PV 데이터 추가!
                # Solver는 Net Load만 보지만, 시각화를 위해 원본 PV 데이터를 결과에 포함시킴
                if params.pv_profile:
                    row['P_PV'] = params.pv_profile[t]
                else:
                    row['P_PV'] = 0.0
                
                output_dict[t] = row
            
            # 최종 저장
            state["solution_output"] = output_dict
            
            print(f"Optimization completed. Cost: {sol.cost:,.0f}")
            print("✅ PV Data added to results.")

        except Exception as e:
            print(f"Solver Error: {e}")
            import traceback
            traceback.print_exc()
            state["solution"] = None

        return state