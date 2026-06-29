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
            state["solver_error"] = None
            state["solver_diagnostic"] = None
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
            state["solution_output"] = None
            diagnostic = self._capacity_diagnostic(params)
            state["solver_diagnostic"] = diagnostic
            state["solver_error"] = f"{e} | {diagnostic}" if diagnostic else str(e)

        return state

    def _capacity_diagnostic(self, params):
        if not params or not getattr(params, "demand_profile", None):
            return ""

        peak_net_demand = max(params.demand_profile)
        gen_capacity = sum(spec.p_max for spec in params.generators.values())
        ess_power = sum(spec.max_power_mw for spec in params.ess.values()) if params.ess else 0.0
        grid_limit = getattr(params, "grid_import_limit_mw", None)
        grid_capacity = float("inf") if grid_limit is None else float(grid_limit)
        available_supply = gen_capacity + ess_power + grid_capacity

        if available_supply == float("inf"):
            return (
                f"Peak net demand {peak_net_demand:.1f} MW; onsite supply "
                f"{gen_capacity + ess_power:.1f} MW plus unbounded grid import."
            )

        if peak_net_demand > available_supply + 1e-6:
            return (
                f"Peak net demand {peak_net_demand:.1f} MW exceeds available supply "
                f"{available_supply:.1f} MW (generators {gen_capacity:.1f} + "
                f"ESS {ess_power:.1f} + grid cap {grid_capacity:.1f}); relax grid import limit."
            )

        return (
            f"Peak net demand {peak_net_demand:.1f} MW is within static available supply "
            f"{available_supply:.1f} MW; infeasibility may involve ramping, SOC, or other constraints."
        )
