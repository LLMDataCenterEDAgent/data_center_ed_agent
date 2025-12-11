# agents/solver_agent.py

import pyomo.environ as pyo
from state.base_state import AgentState

class SolverAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Solver Agent Started ---")
        
        # [수정] state.pyomo_model -> state.get('pyomo_model')
        model = state.get('pyomo_model')
        
        if model is None:
            print("Error: No model found in state.")
            return state

        # Gurobi 호출
        solver = pyo.SolverFactory('gurobi')
        solver.options['TimeLimit'] = 60
        
        try:
            results = solver.solve(model, tee=True)
            
            # agents/solver_agent.py (일부)

            if (results.solver.status == pyo.SolverStatus.ok) and \
               (results.solver.termination_condition == pyo.TerminationCondition.optimal):
                print("Optimal Solution Found!")
                
                solution_data = {}
                for t in model.T:
                    sol_t = {}
                    if hasattr(model, 'P_grid'):
                        sol_t['P_grid'] = pyo.value(model.P_grid[t])
                    if hasattr(model, 'P_mgt'):
                        sol_t['P_mgt'] = pyo.value(model.P_mgt[t])
                    solution_data[t] = sol_t
                
                # 핵심: 'Total_Cost'와 'solution_output'으로 저장
                solution_data['Total_Cost'] = pyo.value(model.Objective)
                state['solution_output'] = solution_data  # 이 이름을 확인하세요!
                state['solution'] = solution_data # 호환성 위해 둘 다 저장
            else:
                print("Solver failed.")
                
        except Exception as e:
            print(f"Solver Error: {e}")

        return state