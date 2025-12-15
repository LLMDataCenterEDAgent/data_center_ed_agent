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
        print("\n--- Formulation Agent Started (Anti-Switching Logic) ---")
        
        # 1. 데이터 가져오기
        data = state.get("parsed_data")
        user_input = state.get("problem_text", "")
        
        if not data:
            print("[Warning] No parsed data. Using defaults.")
            net_demand = [300.0] * 96
            pv_profile = [0.0] * 96
            timestamps = None
        else:
            net_demand = data["net_demand_profile"]
            pv_profile = data["pv_profile"]
            timestamps = data.get("timestamps")

        T = len(net_demand)

        # =========================================================
        # [Step 1] CSV 읽기 (2차 비용 함수)
        # =========================================================
        gt_coeffs = {"a": 0.01, "b": 21.2, "c": 900.0}
        target_file = "gtfuel.csv"
        
        if os.path.exists(target_file):
            print(f">> [System] '{target_file}' 분석 중...")
            try:
                df = pd.read_csv(target_file)
                df.columns = [c.lower().strip() for c in df.columns]
                
                pow_col = next((c for c in df.columns if 'power' in c and 'mw' in c), None)
                cost_col = next((c for c in df.columns if 'cost' in c and 'sec' in c), None)

                if pow_col and cost_col:
                    X_power = pd.to_numeric(df[pow_col], errors='coerce')
                    Y_cost_sec = pd.to_numeric(df[cost_col], errors='coerce')
                    valid_mask = X_power.notnull() & Y_cost_sec.notnull()
                    
                    if valid_mask.any():
                        X_power = X_power[valid_mask]
                        Y_cost_sec = Y_cost_sec[valid_mask]
                        Y_cost_15min = Y_cost_sec * 900.0
                        
                        coeffs = np.polyfit(X_power, Y_cost_15min, 2)
                        gt_coeffs["a"], gt_coeffs["b"], gt_coeffs["c"] = float(coeffs[0]), float(coeffs[1]), float(coeffs[2])
                        print(f"   >> Cost Function: {gt_coeffs['a']:.5f}P^2 + {gt_coeffs['b']:.3f}P + {gt_coeffs['c']:.1f}")
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
        # [Step 3] 발전기 객체 생성 (Symmetry Breaking 적용)
        # =========================================================
        generators = {}
        for conf in gen_configs:
            g_type = conf.get("type", "Gen")
            count = int(conf.get("count", 1))
            
            # 기본 계수 설정
            if g_type == "GT":
                base_a, base_b, base_c = gt_coeffs["a"], gt_coeffs["b"], gt_coeffs["c"]
                ramp = 50.0
            elif g_type == "SMR":
                base_a, base_b, base_c = 0.0, 5.0, 0.0 
                ramp = 0.25
            else:
                base_a, base_b, base_c = 0.0, 50.0, 0.0
                ramp = 100.0

            for i in range(1, count + 1):
                name = f"{g_type}{i}"
                
                # ---------------------------------------------------------
                # [핵심 수정] Symmetry Breaking (대칭 파괴)
                # 동일한 스펙의 발전기가 여러 대일 경우, 뒤번호 발전기에
                # 아주 미세한 추가 비용(Penalty)을 부여하여 순서를 강제함.
                # GT1 -> 기본 비용
                # GT2 -> 기본 비용 + 0.01 (GT1이 다 차야 GT2 가동)
                # ---------------------------------------------------------
                penalty = (i - 1) * 0.01 
                final_b = base_b + penalty
                
                generators[name] = GeneratorSpec(
                    name=name, 
                    a=base_a, 
                    b=final_b,  # 미세한 페널티 적용된 선형 계수
                    c=base_c, 
                    cost_coeff=0.0,
                    p_min=float(conf.get("p_min", 0)),
                    p_max=float(conf.get("p_max", 100)),
                    ramp_rate=float(conf.get("ramp_rate", ramp))
                )
                
                log_msg = f"   + {name} Created"
                if penalty > 0:
                    log_msg += f" (Penalty +{penalty:.4f} applied for priority)"
                print(log_msg)

        # ESS 설정
        ess = {
            "ESS1": StorageSpec(
                name="ESS1", capacity_mwh=160.0, max_power_mw=40.0,
                efficiency=0.95, initial_soc=0.5, 
                min_soc=0.1, max_soc=0.9, aging_cost=10.0
            )
        }

        # =========================================================
        # [Step 4] KEPCO TOU 요금제 (계절 반영)
        # =========================================================
        current_month = 4
        if timestamps:
            try:
                t_str = timestamps[0]
                if "-" in t_str: current_month = int(t_str.split("-")[1])
                elif "/" in t_str: current_month = int(t_str.split("/")[0])
            except: pass
            
        # 계절별 요금 (KRW/MWh)
        SUMMER_RATES = {"light": 120000.0, "mid": 172900.0, "peak": 253800.0}
        SPRING_FALL_RATES = {"light": 120000.0, "mid": 125000.0, "peak": 180000.0}
        WINTER_RATES = {"light": 125000.0, "mid": 170000.0, "peak": 240000.0}

        if current_month in [6, 7, 8]:
            mode, rates = "SUMMER", SUMMER_RATES
        elif current_month in [11, 12, 1, 2]:
            mode, rates = "WINTER", WINTER_RATES
        else:
            mode, rates = "SPRING_FALL", SPRING_FALL_RATES
        
        print(f"   >> [System] Month: {current_month} -> Season: {mode}")

        grid_price_profile = []
        for i in range(T):
            current_hour = 0
            if timestamps:
                try:
                    current_hour = int(timestamps[i].split(" ")[-1].split(":")[0])
                except:
                    current_hour = (9 + int(i/4)) % 24
            else:
                current_hour = (9 + int(i/4)) % 24

            if current_hour >= 23 or current_hour < 9:
                price = rates["light"]
            else:
                if mode == "WINTER":
                    if (10 <= current_hour < 12) or (17 <= current_hour < 20) or (22 <= current_hour < 23):
                        price = rates["peak"]
                    else:
                        price = rates["mid"]
                else:
                    if (10 <= current_hour < 12) or (13 <= current_hour < 17):
                        price = rates["peak"]
                    else:
                        price = rates["mid"]
            grid_price_profile.append(price)

        params = EDParams(
            is_time_series=True, time_steps=T, demand_profile=net_demand, pv_profile=pv_profile,
            grid_price_profile=grid_price_profile,
            timestamps=timestamps, generators=generators, ess=ess
        )
        
        state["params"] = params
        return state