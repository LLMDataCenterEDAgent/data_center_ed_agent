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
            diag = self._capacity_diagnostic(params)
            message = diag.get("message", "") if diag else ""
            state["solver_diagnostic"] = message
            # Capture the capacity diagnosis once, at the first (original-request)
            # failure, so the reported shortfall is relative to the operator's
            # requested grid cap rather than a later relaxed value.
            if diag and diag.get("required_grid_mw") is not None and not state.get("capacity_diagnosis"):
                state["capacity_diagnosis"] = diag
            state["solver_error"] = f"{e} | {message}" if message else str(e)

        return state

    def _capacity_diagnostic(self, params):
        """Diagnose a capacity-limited infeasibility.

        Returns a dict with the peak-net-demand shortfall: the minimum grid
        import required at the peak and how far it exceeds the requested cap.
        """
        if not params or not getattr(params, "demand_profile", None):
            return None

        peak = max(params.demand_profile)
        gen_capacity = sum(spec.p_max for spec in params.generators.values())
        ess_power = sum(spec.max_power_mw for spec in params.ess.values()) if params.ess else 0.0
        local_capacity = gen_capacity + ess_power
        grid_limit = getattr(params, "grid_import_limit_mw", None)
        grid_capacity = float("inf") if grid_limit is None else float(grid_limit)
        available_supply = local_capacity + grid_capacity

        if grid_capacity == float("inf"):
            return {"message": (
                f"Peak net demand {peak:.1f} MW; local capacity "
                f"{local_capacity:.1f} MW plus unbounded grid import."
            )}

        if peak > available_supply + 1e-6:
            required_grid = peak - local_capacity        # e.g. 412.3 - 331 = 81.3 MW
            additional = required_grid - grid_capacity   # e.g. 81.3 - 30 = 51.3 MW
            return {
                "peak_net_demand": peak,
                "local_capacity": local_capacity,
                "required_grid_mw": required_grid,
                "requested_grid_cap_mw": grid_capacity,
                "additional_grid_mw": additional,
                "message": (
                    f"Peak net demand {peak:.1f} MW exceeds local capacity "
                    f"{local_capacity:.1f} MW (generators {gen_capacity:.1f} + ESS {ess_power:.1f}); "
                    f"grid import must supply at least {required_grid:.1f} MW at the peak, "
                    f"{additional:.1f} MW above the {grid_capacity:.0f} MW cap."
                ),
            }

        return {"message": (
            f"Peak net demand {peak:.1f} MW is within static available supply "
            f"{available_supply:.1f} MW; infeasibility may involve ramping, SOC, or other constraints."
        )}
