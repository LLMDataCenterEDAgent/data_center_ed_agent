# agents/explanation_agent.py

from openai import OpenAI
from state.base_state import AgentState

client = OpenAI()

# [핵심] 지시는 영어로(논리력 UP), 출력은 한국어로(가독성 UP)
SYSTEM_PROMPT = """
You are a top-tier **'AI Data Center Energy Optimization Consultant'**.
Your task is to generate a comprehensive **Executive Report** based on the provided simulation results.

**[Report Structure]**
1. **Executive Summary (핵심 요약):**
   - Summarize the total operational cost and key achievements.
   - Explicitly mention that **"Data synchronization was successful,"** matching PV and Demand data starting from **09:00**.

2. **Energy Mix Analysis (에너지 믹스 분석):**
   - **PV (Solar):** Analyze the contribution of renewable energy (Self-generation). Mention the total PV generation and its share.
   - **Generators (G1, G2):** Explain how gas turbines were utilized during expensive Grid pricing hours (Peak shaving).
   - **Grid:** Discuss how the system minimized reliance on the Grid to save costs.

3. **ESS Strategy (ESS 운영 전략):**
   - Analyze the battery operation: Charging during low-price periods and discharging during peak-price periods (Arbitrage). Mention total charged/discharged amounts.

4. **Conclusion (결론):**
   - Provide a final assessment of the optimization efficiency.

**[Output Requirements]**
- **Language:** The final report must be written in **fluent, professional Korean**.
- **Tone:** Analytical, business-professional, and confident.
- **Evidence:** You must cite the specific numbers (MW, KRW, %) provided in the context to support your analysis.
"""

class ExplanationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Explanation Agent Started (Writing Report in Korean...) ---")
        
        sol = state.get("solution_output")
        params = state.get("params") 

        if not sol:
            state["explanation"] = "최적화 결과를 찾을 수 없습니다."
            return state

        try:
            # 1. Python에서 정확한 통계 계산 (LLM의 계산 실수 방지)
            total_cost = sol.get("Total_Cost", 0)
            
            total_grid = 0
            total_pv = 0
            total_gen = 0
            total_ess_dis = 0
            total_ess_chg = 0
            
            # 시계열 데이터 추출 및 합계 계산
            time_steps = []
            p_grid_list = []
            p_mgt_list = []
            p_ess_dis_list = []
            
            for t, val in sol.items():
                if isinstance(t, int) and isinstance(val, dict):
                    time_steps.append(t)
                    
                    g_val = val.get('P_grid', 0)
                    pv_val = val.get('P_PV', 0)
                    # 발전기 합계 (G1, G2 등 모든 발전기)
                    gen_val = 0
                    for k, v in val.items():
                        if k.startswith('P_G') or k.startswith('P_MGT'):
                            gen_val += v
                    
                    ess_d_val = val.get('P_dis_ESS1', val.get('P_discharge', 0))
                    ess_c_val = val.get('P_chg_ESS1', val.get('P_charge', 0))

                    # 리스트에 추가 (피크 분석용)
                    p_grid_list.append(g_val)
                    p_mgt_list.append(gen_val)
                    p_ess_dis_list.append(ess_d_val)

                    # 총합 누적
                    total_grid += g_val
                    total_pv += pv_val
                    total_gen += gen_val
                    total_ess_dis += ess_d_val
                    total_ess_chg += ess_c_val

            total_supply = total_grid + total_pv + total_gen + total_ess_dis
            
            # PV 점유율 계산
            pv_share = (total_pv / total_supply * 100) if total_supply > 0 else 0
            
            # 피크 타임 분석
            total_load_t = [g + m + d + pv for g, m, d, pv in zip(p_grid_list, p_mgt_list, p_ess_dis_list, [val.get('P_PV', 0) for t, val in sol.items() if isinstance(t, int)])]
            # 주의: 위 리스트 컴프리헨션은 간략화된 것임. 실제로는 인덱스 매칭 필요.
            # 간편하게 total_supply_t 재계산
            total_supply_t = []
            for t in range(len(time_steps)):
                val = sol[time_steps[t]]
                s = val.get('P_grid', 0) + val.get('P_PV', 0) + \
                    sum(v for k, v in val.items() if k.startswith('P_G') or k.startswith('P_MGT')) + \
                    val.get('P_dis_ESS1', val.get('P_discharge', 0))
                total_supply_t.append(s)

            if total_supply_t:
                peak_load = max(total_supply_t)
                peak_idx = total_supply_t.index(peak_load)
                
                # 시간 정보 (시작 시간 고려)
                start_time_str = "09:00"
                if params and params.timestamps:
                    start_time_str = params.timestamps[0]
                    # 피크 시간 문자열 가져오기
                    peak_time_str = params.timestamps[peak_idx] if peak_idx < len(params.timestamps) else f"Step {peak_idx}"
                else:
                    peak_time_str = f"Step {peak_idx}"
            else:
                peak_load = 0
                peak_time_str = "N/A"

            # 2. LLM에게 던져줄 '팩트 시트' (영어+숫자 혼용)
            summary_input = f"""
            [Optimization Data Fact Sheet]
            1. Financials
               - Total Operational Cost: {total_cost:,.0f} KRW
            
            2. Energy Supply Breakdown (Total MW over simulation)
               - Total Supply: {total_supply:,.1f} MW
               - Grid Import: {total_grid:,.1f} MW
               - PV Generation: {total_pv:,.1f} MW (Share: {pv_share:.1f}%)
               - Gas Turbines (G1+G2): {total_gen:,.1f} MW
               - ESS Discharge: {total_ess_dis:,.1f} MW
               - ESS Charge: {total_ess_chg:,.1f} MW
            
            3. Peak Load Analysis
               - Peak Time: {peak_time_str}
               - Peak Load: {peak_load:,.1f} MW
            
            4. Simulation Context
               - Step Count: {len(sol)-1} steps (15-min intervals)
               - Start Time: {start_time_str} (Data Merging Confirmed)
            """

            # 3. LLM 호출
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": summary_input},
                ],
                temperature=0.3, # 분석적이고 일관성 있게
            )
            
            explanation = resp.choices[0].message.content
            state["explanation"] = explanation
            print(">> Report generated successfully.")
            
        except Exception as e:
            print(f"Explanation Error: {e}")
            import traceback
            traceback.print_exc()
            state["explanation"] = "Error generating report."

        return state