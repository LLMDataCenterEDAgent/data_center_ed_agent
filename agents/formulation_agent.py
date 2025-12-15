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
        print("\n--- Formulation Agent Started (Fixed Base Cost Applied) ---")
        
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
        gt_coeffs = {"a": 0.0, "b": 0.0, "c": 0.0}
        target_file = "gtfuel.csv"
        EXCHANGE_RATE = 1300.0 
        
        if os.path.exists(target_file):
            print(f">> [System] '{target_file}' 분석 중...")
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
                        # $/sec -> KRW/15min
                        Y_cost_KRW_15min = Y_cost_sec * EXCHANGE_RATE * 900.0
                        
                        coeffs = np.polyfit(X_power, Y_cost_KRW_15min, 2)
                        gt_coeffs["a"] = float(coeffs[0])
                        gt_coeffs["b"] = float(coeffs[1])
                        gt_coeffs["c"] = float(coeffs[2])
                        print(f"   >> GT Cost (KRW/15min): {gt_coeffs['a']:.2f}P^2 + {gt_coeffs['b']:.0f}P + {gt_coeffs['c']:.0f}")
            except Exception as e:
                print(f"   >> [Error] CSV Read Failed: {e}")

        # =========================================================
        # [Step 2] 사용자 입력 파싱
        # =========================================================
        gen_configs = []
        if user_input:
            try:
                PROMPT = """Extract generator specs to JSON 'generators' list: type, count, p_min, p_max."""
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": user_input}],
                    temperature=0.0
                )
                content = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
                gen_configs = json.loads(content).get("generators", [])
            except: pass

        if not gen_configs:
            gen_configs = [
                {"type": "GT", "count": 2, "p_min": 85, "p_max": 170},
                {"type": "SMR", "count": 1, "p_min": 91, "p_max": 121}
            ]

        # =========================================================
        # [Step 3] 발전기 생성
        # =========================================================
        generators = {}
        for conf in gen_configs:
            g_type = conf.get("type", "Gen")
            count = int(conf.get("count", 1))
            
            if g_type == "GT":
                base_a, base_b, base_c = gt_coeffs["a"], gt_coeffs["b"], gt_coeffs["c"]
                ramp = 50.0
            elif g_type == "SMR":
                base_a, base_b, base_c = 0.0, 2500.0, 0.0 
                ramp = 0.75 
            else:
                base_a, base_b, base_c = 0.0, 50000.0, 0.0
                ramp = 100.0

            for i in range(1, count + 1):
                name = f"{g_type}{i}"
                penalty = (i - 1) * 10.0 
                final_b = base_b + penalty
                
                generators[name] = GeneratorSpec(
                    name=name, a=base_a, b=final_b, c=base_c, cost_coeff=0.0,
                    p_min=float(conf.get("p_min", 0)),
                    p_max=float(conf.get("p_max", 100)),
                    ramp_rate=float(conf.get("ramp_rate", ramp))
                )

        # ESS 설정
        ess = {
            "ESS1": StorageSpec(
                name="ESS1", capacity_mwh=160.0, max_power_mw=40.0,
                efficiency=0.95, initial_soc=0.5, 
                min_soc=0.1, max_soc=0.9, aging_cost=5000.0
            )
        }

        # =========================================================
        # [Step 4] KEPCO TOU & Base Cost
        # =========================================================
        current_month = 4
        if timestamps:
            try:
                t_str = timestamps[0]
                if "-" in t_str: current_month = int(t_str.split("-")[1])
                elif "/" in t_str: current_month = int(t_str.split("/")[0])
                print(f"   >> [System] Detected Month: {current_month}")
            except: pass
            
        SUMMER = {"light": 120000.0, "mid": 190000.0, "peak": 350000.0}
        SPRING = {"light": 120000.0, "mid": 140000.0, "peak": 280000.0}
        WINTER = {"light": 125000.0, "mid": 180000.0, "peak": 320000.0}

        if current_month in [6, 7, 8]:
            mode, rates_mwh = "SUMMER", SUMMER
        elif current_month in [11, 12, 1, 2]:
            mode, rates_mwh = "WINTER", WINTER
        else:
            mode, rates_mwh = "SPRING_FALL", SPRING
        
        rates_15min = {k: v / 4.0 for k, v in rates_mwh.items()}
        print(f"   >> [System] Season: {mode} (Peak: {rates_15min['peak']:.0f} KRW/15min)")

        grid_price_profile = []
        for i in range(T):
            h = 0
            if timestamps:
                try: h = int(timestamps[i].split(" ")[-1].split(":")[0])
                except: h = (9 + int(i/4)) % 24
            else: h = (9 + int(i/4)) % 24

            if h >= 23 or h < 9:
                price = rates_15min["light"]
            else:
                if mode == "WINTER":
                    if (10 <= h < 12) or (17 <= h < 20) or (22 <= h < 23): price = rates_15min["peak"]
                    else: price = rates_15min["mid"]
                else:
                    if (10 <=  h < 17): price = rates_15min["peak"]
                    else: price = rates_15min["mid"]
            grid_price_profile.append(price)

        # [핵심 수정] 요청하신 고정 기본요금 반영
        FIXED_BASE_COST = 107866666.0
        print(f"   >> [Cost] Fixed Base Cost Set: {FIXED_BASE_COST:,.0f} KRW")

        params = EDParams(
            is_time_series=True, time_steps=T, demand_profile=net_demand, pv_profile=pv_profile,
            grid_price_profile=grid_price_profile, timestamps=timestamps, generators=generators, ess=ess,
            base_rate=FIXED_BASE_COST
        )
        
        state["params"] = params
        return state