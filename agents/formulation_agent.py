# agents/formulation_agent.py

from core.pyomo_model import PyomoModelBuilder
from state.base_state import AgentState

class FormulationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Formulation Agent Started ---")
        
        params = state.get("params")
        if not params:
            print("Error: No params found in state.")
            return state

        # Pyomo 모델 빌더 호출
        builder = PyomoModelBuilder()
        
        try:
            # 시계열 동적 모델 생성
            model = builder.create_time_series_model(params)
            
            # 생성된 모델을 State에 저장 (Solver Agent가 사용)
            state["pyomo_model"] = model
            print("Pyomo model successfully built.")
            
        except Exception as e:
            print(f"Formulation Error: {e}")
            state["pyomo_model"] = None

        return state