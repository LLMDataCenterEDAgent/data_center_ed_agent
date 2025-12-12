# agents/formulation_agent.py

from state.base_state import AgentState
from state.schemas import EDParams, GeneratorSpec, StorageSpec, RenewableSpec

class FormulationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Formulation Agent Started (SMR & GT Logic Applied) ---")
        
        data = state.get("parsed_data")
        if not data:
            print("No parsed data found. Using defaults.")
            net_demand = [300.0] * 96
            pv_profile = [0.0] * 96
            timestamps = None
        else:
            net_demand = data["net_demand_profile"]
            pv_profile = data["pv_profile"]
            timestamps = data.get("timestamps")

        T = len(net_demand)

        # ---------------------------------------------------------
        # [핵심 수정] 사용자 메모 스펙 반영 (GT 2대, SMR 1대)
        # ---------------------------------------------------------
        generators = {}
        
        # 1. 가스터빈 (GT) 2대
        # Cost: 0.03 $/MW (선형), Range: 85 ~ 120 MW
        # Ramp Rate는 메모에 없으므로, 유연한 운전을 위해 기존 100MW/15min 유지 (혹은 제거)
        for i in range(1, 3):
            generators[f"GT{i}"] = GeneratorSpec(
                name=f"GT{i}", 
                a=0, b=0, c=0, # 2차 함수 아님
                cost_coeff=0.03, # 선형 비용 ($/MW)
                p_min=85, 
                p_max=170, 
                ramp_rate=50 # GT는 비교적 유연함 (가정값)
            )

        # 2. SMR (소형모듈원전) 1대
        # Cost: 0.002 $/MW (매우 저렴), Range: 91 ~ 121 MW
        # Ramp Rate: 0.25 MW/15min (매우 경직됨 -> 기저부하 역할)
        generators["SMR1"] = GeneratorSpec(
            name="SMR1", 
            a=0, b=0, c=0,
            cost_coeff=0.002, # 선형 비용 ($/MW)
            p_min=91, 
            p_max=121, 
            ramp_rate=0.25 # [중요] 동특성 반영 (출력 변동 제한)
        )

        # ---------------------------------------------------------
        
        params = EDParams(
            is_time_series=True,
            time_steps=T,
            demand_profile=net_demand,
            pv_profile=pv_profile,
            
            # Grid Price는 기존 유지 (낮 150, 밤 50) - SMR($0.002)이 훨씬 쌈!
            grid_price_profile=[150.0 if 36 <= i <= 72 else 50.0 for i in range(T)],
            timestamps=timestamps,
            
            generators=generators,
            
            ess={
                "ESS1": StorageSpec(
                    name="ESS1", capacity_mwh=160.0, max_power_mw=40.0,
                    efficiency=0.95, initial_soc=0.5, 
                    min_soc=0.1, max_soc=0.9, aging_cost=10.0
                )
            }
        )
        
        state["params"] = params
        print(f"EDParams Created with SMR & GTs. Steps: {T}")
        return state