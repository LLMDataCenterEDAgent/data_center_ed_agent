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
            print(f">>> Solving Dynamic ED for {len(params.generators)} gens...")
            sol = solve_dynamic_ed(params)
            
            state["solution"] = sol
            
            # 결과 변환 (Dict)
            output_dict = {}
            output_dict['Total_Cost'] = sol.cost
            
            # 동적 키 생성
            gen_names = list(params.generators.keys())
            ess_names = list(params.ess.keys()) if params.ess else []

            for t in range(params.time_steps):
                row = {}
                row['P_grid'] = sol.schedule.get('P_grid', [0]*params.time_steps)[t]
                
                # 발전기
                for g in gen_names:
                    key = f'P_{g}'
                    if key in sol.schedule:
                        row[key] = sol.schedule[key][t]
                    else:
                        row[key] = 0.0
                
                # ESS
                if sol.ess_schedule:
                    for e in ess_names:
                        if e in sol.ess_schedule:
                            row[f'P_dis_{e}'] = sol.ess_schedule[e]['discharge'][t]
                            row[f'P_chg_{e}'] = sol.ess_schedule[e]['charge'][t]
                            row[f'SOC_{e}'] = sol.ess_schedule[e]['soc'][t]
                
                # PV
                if params.pv_profile:
                    row['P_PV'] = params.pv_profile[t]
                else:
                    row['P_PV'] = 0.0
                
                output_dict[t] = row
            
            state["solution_output"] = output_dict
            print(f"Optimization completed. Cost: {sol.cost:,.0f} KRW")

        except Exception as e:
            print(f"Solver Error: {e}")
            import traceback
            traceback.print_exc()
            state["solution"] = None

        return state