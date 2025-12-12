# agents/formulation_agent.py

from state.base_state import AgentState
from state.schemas import EDParams, GeneratorSpec, StorageSpec, RenewableSpec

class FormulationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Formulation Agent Started ---")
        
        data = state.get("parsed_data")
        if not data:
            print("No parsed data found. Using defaults.")
            net_demand = [300.0] * 96
            pv_profile = [0.0] * 96
            timestamps = None
        else:
            net_demand = data["net_demand_profile"]
            pv_profile = data["pv_profile"]
            # [핵심 수정] ParsingAgent가 넘겨준 시간표를 받습니다.
            timestamps = data.get("timestamps") 

        # 데이터 길이만큼만 타임스텝 설정 (예: 60개면 60개)
        T = len(net_demand)

        params = EDParams(
            is_time_series=True,
            time_steps=T,
            demand_profile=net_demand,
            pv_profile=pv_profile,
            grid_price_profile=[150.0 if 36 <= i <= 72 else 50.0 for i in range(T)],
            
            # [핵심 수정] 시간표를 파라미터 객체에 담습니다!
            timestamps=timestamps, 
            
            generators={
                "G1": GeneratorSpec(name="G1", a=0.001, b=0.5, c=3, p_min=100, p_max=300),
                "G2": GeneratorSpec(name="G2", a=0.002, b=0.3, c=5, p_min=150, p_max=300),
            },
            ess={
                "ESS1": StorageSpec(
                    name="ESS1", capacity_mwh=160.0, max_power_mw=40.0,
                    efficiency=0.95, initial_soc=0.5, 
                    min_soc=0.1, max_soc=0.9, aging_cost=10.0
                )
            }
        )
        
        state["params"] = params
        print(f"EDParams Created. Time Steps: {T} (Range: {timestamps[0]} ~ {timestamps[-1]} if valid)")
        return state