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
        print("\n--- Formulation Agent Started (Full-Data CSV Mode) ---")
        
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
        # [핵심] fuel.csv (전체 데이터 포함) 읽기
        # =========================================================
        gt_coeffs = {"a": 0.01, "b": 21.2, "c": 900.0} # 기본값
        target_file = "gtfuel.csv"
        
        if os.path.exists(target_file):
            print(f">> [System] '{target_file}' 파일에서 비용 데이터를 분석합니다.")
            try:
                df = pd.read_csv(target_file)
                
                # 컬럼명 소문자 변환 및 공백 제거 (안전장치)
                df.columns = [c.lower().strip() for c in df.columns]
                
                # 필요한 컬럼만 찾아서 사용 (power_mw, cost_usd_per_sec)
                # 나머지 컬럼(fuel_kg 등)은 파일에 있어도 무시하고 넘어감
                if 'power_mw' in df.columns and 'cost_usd_per_sec' in df.columns:
                    X_power = df['power_mw']
                    Y_cost_sec = df['cost_usd_per_sec']
                    
                    # 데이터 정제
                    valid_mask = pd.to_numeric(X_power, errors='coerce').notnull() & pd.to_numeric(Y_cost_sec, errors='coerce').notnull()
                    X_power = X_power[valid_mask].astype(float)
                    Y_cost_sec = Y_cost_sec[valid_mask].astype(float)

                    if len(X_power) > 0:
                        # 단위 변환 ($/s -> $/15min)
                        Y_cost_15min = Y_cost_sec * 900
                        
                        # 회귀분석
                        coeffs = np.polyfit(X_power, Y_cost_15min, 2)
                        gt_coeffs["a"] = float(coeffs[0])
                        gt_coeffs["b"] = float(coeffs[1])
                        gt_coeffs["c"] = float(coeffs[2])
                        
                        print(f"   >> 분석 성공! (전체 데이터 중 비용 컬럼만 추출)")
                        print(f"   >> Cost Function: {gt_coeffs['a']:.5f}P^2 + {gt_coeffs['b']:.3f}P + {gt_coeffs['c']:.1f}")
                    else:
                        print("   >> [Error] 유효한 데이터 행이 없습니다.")
                else:
                    print("   >> [Error] 'power_mw' 또는 'cost_usd_per_sec' 컬럼을 찾을 수 없습니다.")
                    print(f"   >> 발견된 컬럼: {list(df.columns)}")
                    
            except Exception as e:
                print(f"   >> [Error] 파일 읽기 실패: {e}")
        else:
            print(f"   >> [Warning] '{target_file}'이 없습니다. 기본값을 사용합니다.")

        # =========================================================
        # [설정 로드]
        # =========================================================
        gen_configs = []
        if user_input:
            try:
                PROMPT = """Extract generator specs to JSON. Output keys: type, count, p_min, p_max. Ignore cost."""
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
                {"type": "GT", "count": 2, "p_min": 85, "p_max": 120, "ramp_rate": 50},
                {"type": "SMR", "count": 1, "p_min": 91, "p_max": 121, "ramp_rate": 0.25}
            ]

        # =========================================================
        # [객체 생성]
        # =========================================================
        generators = {}
        for conf in gen_configs:
            g_type = conf.get("type", "Gen")
            count = int(conf.get("count", 1))
            
            # GT에 분석된 계수 적용
            if g_type == "GT":
                a, b, c = gt_coeffs["a"], gt_coeffs["b"], gt_coeffs["c"]
            elif g_type == "SMR":
                a, b, c = 0.0, 5.0, 0.0 
            else:
                a, b, c = 0.0, 50.0, 0.0

            for i in range(1, count + 1):
                name = f"{g_type}{i}"
                generators[name] = GeneratorSpec(
                    name=name, a=a, b=b, c=c, cost_coeff=0.0,
                    p_min=float(conf.get("p_min", 0)),
                    p_max=float(conf.get("p_max", 100)),
                    ramp_rate=float(conf.get("ramp_rate", 100))
                )
                print(f"   + {name} Created (Cost Function Applied)")

        ess = {
            "ESS1": StorageSpec(
                name="ESS1", capacity_mwh=160.0, max_power_mw=40.0,
                efficiency=0.95, initial_soc=0.5, 
                min_soc=0.1, max_soc=0.9, aging_cost=10.0
            )
        }

        params = EDParams(
            is_time_series=True, time_steps=T, demand_profile=net_demand, pv_profile=pv_profile,
            grid_price_profile=[150.0 if 36 <= i <= 72 else 50.0 for i in range(T)],
            timestamps=timestamps, generators=generators, ess=ess
        )
        
        state["params"] = params
        return state