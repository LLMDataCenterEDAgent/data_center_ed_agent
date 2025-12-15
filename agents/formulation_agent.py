# agents/formulation_agent.py

import json
import os
import pandas as pd
import numpy as np
from openai import OpenAI
from state.base_state import AgentState
from state.schemas import EDParams, GeneratorSpec, StorageSpec

client = OpenAI()

class FormulationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Formulation Agent Started (Unit Fix + Ramp 0.75) ---")
        
        # 1. 데이터 가져오기
        data = state.get("parsed_data")
        user_input = state.get("problem_text", "")
        
        if not data:
            net_demand = [300.0] * 96
            pv_profile = [0.0] * 96
            timestamps = None
        else:
            net_demand = data["net_demand_profile"]
            pv_profile = data["pv_profile"]
            timestamps = data.get("timestamps")

        T = len(net_demand)

        # =========================================================
        # [Step 1] GT 비용 함수 (KRW/15min)
        # =========================================================
        gt_coeffs = {"a": 10.0, "b": 15000.0, "c": 50000.0}
        target_file = "gtfuel.csv"
        EXCHANGE_RATE = 1300.0
        
        if os.path.exists(target_file):
            try:
                df = pd.read_csv(target_file)
                df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
                pow_col = next((c for c in df.columns if 'power' in c and 'mw' in c), None)
                cost_col = next((c for c in df.columns if 'cost' in c and 'sec' in c), None)

                if pow_col and cost_col:
                    X_power = pd.to_numeric(df[pow_col], errors='coerce')
                    Y_cost_sec = pd.to_numeric(df[cost_col], errors='coerce')
                    valid_mask = X_power.notnull() & Y_cost_sec.notnull()
                    
                    if valid_mask.any():
                        X_power = X_power[valid_mask]
                        Y_cost_sec = Y_cost_sec[valid_mask]
                        # $/s -> KRW/15min (x900)
                        Y_cost_KRW_15min = Y_cost_sec * EXCHANGE_RATE * 900.0
                        
                        coeffs = np.polyfit(X_power, Y_cost_KRW_15min, 2)
                        gt_coeffs["a"], gt_coeffs["b"], gt_coeffs["c"] = float(coeffs[0]), float(coeffs[1]), float(coeffs[2])
                        print(f"   >> [GT Cost] a={gt_coeffs['a']:.2f}, b={gt_coeffs['b']:.0f} (KRW/15min)")
            except: pass

        # =========================================================
        # [Step 2] 사용자 입력
        # =========================================================
        gen_configs = []
        if user_input:
            try:
                PROMPT = "Extract generator specs to JSON 'generators' list: type, count, p_min, p_max."
                resp = client.chat.completions.create(
                    model="gpt-4o", messages=[{"role":"system","content":PROMPT},{"role":"user","content":user_input}]
                )
                content = resp.choices[0].message.content.strip().replace("```json","").replace("```","")
                gen_configs = json.loads(content).get("generators", [])
            except: pass

        if not gen_configs:
            gen_configs = [{"type": "GT", "count": 2}, {"type": "SMR", "count": 1}]

        # =========================================================
        # [Step 3] 발전기 생성 (SMR Ramp=0.75, Cost=2500)
        # =========================================================
        generators = {}
        for conf in gen_configs:
            g_type = conf.get("type", "Gen")
            count = int(conf.get("count", 1))
            
            if g_type == "SMR":
                # SMR: 10,000원/MWh -> 2,500원/MW/15min
                final_a, final_b, final_c = 0.0, 2500.0, 0.0
                final_p_min, final_p_max = 100.0, 121.0
                # [수정] Ramp Rate 0.75
                final_ramp = 0.75 
                print(f"   >> [SMR] Cost=2500, Ramp={final_ramp} (Fixed)")
                
            elif g_type == "GT":
                final_a, final_b, final_c = gt_coeffs["a"], gt_coeffs["b"], gt_coeffs["c"]
                final_p_min = float(conf.get("p_min", 85))
                final_p_max = float(conf.get("p_max", 170))
                final_ramp = float(conf.get("ramp_rate", 50.0))
            else:
                final_a, final_b, final_c = 0.0, 50000.0, 0.0
                final_p_min, final_p_max = 0.0, 100.0
                final_ramp = 100.0

            for i in range(1, count + 1):
                name = f"{g_type}{i}"
                penalty = (i - 1) * 10.0 # 대칭 파괴
                generators[name] = GeneratorSpec(
                    name=name, a=final_a, b=final_b+penalty, c=final_c,
                    p_min=final_p_min, p_max=final_p_max, ramp_rate=final_ramp
                )

        # ESS
        ess = {
            "ESS1": StorageSpec(
                name="ESS1", capacity_mwh=160.0, max_power_mw=40.0,
                efficiency=0.95, initial_soc=0.5, min_soc=0.1, max_soc=0.9, aging_cost=5000.0
            )
        }

        # =========================================================
        # [Step 4] KEPCO 요금제 (15분 단위로 /4 변환)
        # =========================================================
        current_month = 4
        if timestamps:
            try: current_month = int(timestamps[0].split("-")[1])
            except: pass
            
        SUMMER = {"light": 120000, "mid": 190000, "peak": 350000}
        SPRING = {"light": 120000, "mid": 140000, "peak": 280000}
        WINTER = {"light": 125000, "mid": 180000, "peak": 320000}

        if current_month in [6, 7, 8]: rates = SUMMER
        elif current_month in [11, 12, 1, 2]: rates = WINTER
        else: rates = SPRING
        
        # [중요] 15분 단위 변환
        rates_15min = {k: v/4.0 for k,v in rates.items()}
        print(f"   >> [Grid] Peak Price: {rates['peak']} -> {rates_15min['peak']:.0f} KRW/15min")

        grid_price = []
        for i in range(T):
            h = (9 + int(i/4)) % 24
            if timestamps:
                try: h = int(timestamps[i].split(" ")[-1].split(":")[0])
                except: pass

            if h >= 23 or h < 9: p = rates_15min["light"]
            else:
                if current_month in [11,12,1,2]: # Winter
                    p = rates_15min["peak"] if h in [10,11,17,18,19,22] else rates_15min["mid"]
                else:
                    p = rates_15min["peak"] if h in [10,11,13,14,15,16] else rates_15min["mid"]
            grid_price.append(p)

        state["params"] = EDParams(
            is_time_series=True, time_steps=T, demand_profile=net_demand, pv_profile=pv_profile,
            grid_price_profile=grid_price, timestamps=timestamps, generators=generators, ess=ess
        )
        return state