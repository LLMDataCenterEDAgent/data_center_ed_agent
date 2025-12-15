# agents/explanation_agent.py

from openai import OpenAI
from state.base_state import AgentState
import numpy as np

client = OpenAI()

# [프롬프트 대폭 강화] 구체적이고 풍부한 분석 요청
SYSTEM_PROMPT = """
You are an expert 'AI Data Center Energy Consultant'.
Your task is to generate a comprehensive 'Energy Optimization Executive Report' in Korean.

The report MUST include:
1.  **Cost Breakdown (Important)**:
    - Explicitly mention the **Fixed Base Cost (기본요금)**: 107,866,666 KRW.
    - Analyze the **Variable Cost (전력량요금 + 연료비)** separated from the total.
    - Total Cost = Fixed Base Cost + Variable Cost.

2.  **TOU (Time-of-Use) Strategy Analysis**:
    - Provide a detailed analysis for each time period: **Light(경부하), Mid(중간부하), Peak(최대부하)**.
    - Explain *WHY* the system chose specific power sources in each period based on prices.
    - Example: "In the Peak period (Price: XX KRW), GT generation was maximized because it is cheaper (~37,000 KRW) than Grid power."

3.  **Operational Insights**:
    - Explain the role of **SMR** (Baseload, due to low cost).
    - Explain the role of **ESS** (Peak shaving / Arbitrage).

Use the specific numbers provided in the [Data Section] below. Do not hallucinate numbers.
"""

class ExplanationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Explanation Agent Started (Rich Content Mode) ---")
        
        sol = state.get("solution_output")
        params = state.get("params") 

        if not sol or not params:
            state["explanation"] = "데이터 부족."
            return state

        try:
            # 1. 비용 데이터 분해
            total_cost_final = sol.get("Total_Cost", 0)
            fixed_base_cost = params.base_rate if params.base_rate else 0
            variable_cost = total_cost_final - fixed_base_cost
            
            gen_names = list(params.generators.keys())
            ess_names = list(params.ess.keys()) if params.ess else []
            T = params.time_steps
            
            # 2. TOU(시간대별) 상세 분석
            prices = params.grid_price_profile if params.grid_price_profile else [0]*T
            unique_prices = sorted(list(set(prices)))
            
            tou_map = {} 
            if len(unique_prices) >= 3:
                tou_map[unique_prices[0]] = 'Light (경부하)'
                tou_map[unique_prices[-1]] = 'Peak (최대부하)'
                for p in unique_prices[1:-1]: tou_map[p] = 'Mid (중간부하)'
            elif len(unique_prices) == 2:
                tou_map[unique_prices[0]] = 'Light'
                tou_map[unique_prices[-1]] = 'Peak'
            else:
                tou_map[unique_prices[0]] = 'Flat'
            
            tou_stats = {}
            total_supply = 0
            
            for t in range(T):
                p = prices[t]
                label = tou_map.get(p, 'Unknown')
                if label not in tou_stats:
                    tou_stats[label] = {'count':0, 'grid':0, 'gen':0, 'ess':0, 'price':p}
                
                row = sol.get(t, {})
                if not row: continue
                
                p_grid = row.get('P_grid', 0)
                p_gen_sum = sum(row.get(f'P_{g}', 0) for g in gen_names)
                p_ess_dis = sum(row.get(f'P_dis_{e}', 0) for e in ess_names)
                
                tou_stats[label]['count'] += 1
                tou_stats[label]['grid'] += p_grid
                tou_stats[label]['gen'] += p_gen_sum
                tou_stats[label]['ess'] += p_ess_dis
                
                total_supply += (p_grid + row.get('P_PV', 0) + p_gen_sum + p_ess_dis)

            # 3. LLM 입력 데이터 생성
            tou_summary_str = ""
            for label, stat in tou_stats.items():
                if stat['count'] > 0:
                    avg_grid = stat['grid'] / stat['count']
                    avg_gen = stat['gen'] / stat['count']
                    avg_ess = stat['ess'] / stat['count']
                    
                    tou_summary_str += f"""
                    [{label}]
                    - Grid Price: {stat['price']:.1f} KRW/MW/15min
                    - Duration: {stat['count'] * 15} mins
                    - Avg Power Mix: Grid {avg_grid:.1f} MW | Gen {avg_gen:.1f} MW | ESS Discharge {avg_ess:.1f} MW
                    """

            summary_input = f"""
            [Financial Summary]
            - **Grand Total Cost**: {total_cost_final:,.0f} KRW
            - **Fixed Base Cost (기본요금)**: {fixed_base_cost:,.0f} KRW (Included in Total)
            - **Variable Operating Cost**: {variable_cost:,.0f} KRW
            
            [Energy Statistics]
            - Total Energy Supplied: {total_supply:,.1f} MW (integrated over 24h)
            
            [Detailed TOU Analysis Data]
            {tou_summary_str}
            
            [Asset Info]
            - Generators: {', '.join(gen_names)} (SMR Cost: ~2,500 KRW, GT Cost: ~37,000 KRW)
            - ESS: {', '.join(ess_names)}
            """

            # 4. LLM 호출
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": summary_input},
                ],
                temperature=0.3,
            )
            
            explanation = resp.choices[0].message.content
            state["explanation"] = explanation
            print(">> Explanation Generated with Rich Content & Fixed Cost.")
            
        except Exception as e:
            print(f"Explanation Error: {e}")
            import traceback
            traceback.print_exc()
            state["explanation"] = "Error generating explanation."

        return state