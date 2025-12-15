# agents/explanation_agent.py

from openai import OpenAI
from state.base_state import AgentState

client = OpenAI()

SYSTEM_PROMPT = """
You are a top-tier **'AI Data Center Energy Optimization Consultant'**.
Your task is to generate a comprehensive **Executive Report** based on the provided simulation results.

**[Report Structure]**
1. **Executive Summary:** Summarize cost and key achievements.
2. **Energy Mix Analysis:** Analyze PV, Generators (GT, SMR, etc.), and Grid usage.
3. **ESS Strategy:** Analyze battery operation.
4. **Conclusion:** Final assessment.

**[Output Requirements]**
- **Language:** Fluent, professional Korean.
- **Evidence:** Cite specific numbers (MW, KRW, %).
"""

class ExplanationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Explanation Agent Started (Dynamic Analysis) ---")
        
        sol = state.get("solution_output")
        params = state.get("params") 

        if not sol or not params:
            state["explanation"] = "데이터 부족으로 보고서를 작성할 수 없습니다."
            return state

        try:
            # 1. 통계 집계 (동적)
            total_cost = sol.get("Total_Cost", 0)
            
            total_grid = 0
            total_pv = 0
            total_gen = 0
            total_ess_dis = 0
            
            # 동적 리스트 확인
            gen_names = list(params.generators.keys())
            ess_names = list(params.ess.keys()) if params.ess else []
            
            for t, val in sol.items():
                if isinstance(t, int) and isinstance(val, dict):
                    # 고정 항목
                    total_grid += val.get('P_grid', 0)
                    total_pv += val.get('P_PV', 0)
                    
                    # 발전기 합계 (GT1 + SMR1 + ...)
                    for g in gen_names:
                        total_gen += val.get(f'P_{g}', 0)
                    
                    # ESS 방전 합계
                    for e in ess_names:
                        total_ess_dis += val.get(f'P_dis_{e}', 0)

            total_supply = total_grid + total_pv + total_gen + total_ess_dis
            pv_share = (total_pv / total_supply * 100) if total_supply > 0 else 0
            
            # 피크 타임 분석
            peak_load = 0
            peak_time_str = "N/A"
            
            # 시간별 부하 계산
            temp_loads = []
            for t in range(params.time_steps):
                val = sol[t]
                current_load = val.get('P_grid', 0) + val.get('P_PV', 0)
                for g in gen_names: current_load += val.get(f'P_{g}', 0)
                for e in ess_names: current_load += val.get(f'P_dis_{e}', 0)
                temp_loads.append(current_load)
                
            if temp_loads:
                peak_load = max(temp_loads)
                peak_idx = temp_loads.index(peak_load)
                if params.timestamps:
                    peak_time_str = params.timestamps[peak_idx]
                else:
                    peak_time_str = f"Step {peak_idx}"

            # 2. LLM 입력 데이터 작성
            summary_input = f"""
            [Optimization Data Fact Sheet]
            1. Simulation Scope
               - Generators: {', '.join(gen_names)}
               - ESS Units: {', '.join(ess_names) if ess_names else 'None'}
               - Time Steps: {params.time_steps}
            
            2. Financials
               - Total Cost: {total_cost:,.0f} KRW
            
            3. Supply Breakdown (Total MW)
               - Total Supply: {total_supply:,.1f} MW
               - Grid: {total_grid:,.1f} MW
               - PV: {total_pv:,.1f} MW ({pv_share:.1f}%)
               - Generators ({', '.join(gen_names)}): {total_gen:,.1f} MW
               - ESS Discharge: {total_ess_dis:,.1f} MW
            
            4. Peak Analysis
               - Peak Time: {peak_time_str}
               - Peak Load: {peak_load:,.1f} MW
            """

            # 3. LLM 호출
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
            print(">> Report generated successfully.")
            
        except Exception as e:
            print(f"Explanation Error: {e}")
            import traceback
            traceback.print_exc()
            state["explanation"] = "Error."

        return state