# agents/explanation_agent.py

from openai import OpenAI
from state.base_state import AgentState

client = OpenAI()

# [프롬프트 강화] 단순 요약이 아니라 '전략적 가치'를 증명하도록 지시
SYSTEM_PROMPT = """
You are a Senior Energy Consultant specializing in AI Data Center Optimization.
Your goal is to write a **high-impact executive summary** based on the provided optimization results.

**Rules for the Report:**
1. **Be Specific:** Never say "costs were optimized." Say "Costs were reduced by leveraging MGT during peak hours."
2. **Use Numbers:** Always quote the provided MW and Cost figures to support your arguments.
3. **Analyze Strategy:**
   - **Arbitrage:** Did the system charge ESS when cheap and discharge when expensive?
   - **Peak Shaving:** Did MGT/ESS replace Grid during peak load times?
   - **Resilience:** If a resource (like ESS) is missing/zero, explain how the system survived without it.

**Output Structure:**
### 1. Executive Summary (핵심 요약)
- Overall operational cost and average unit cost.
- Key strategy used (e.g., "Aggressive Peak Shaving" or "Grid-Dominant Sourcing").

### 2. Energy Mix & Reliability (에너지 믹스 및 안정성)
- Breakdown of power sources (Grid vs. Self-Generation).
- Peak Load Analysis: How was the highest demand met? (e.g., "At peak time (14:00), MGT provided 40% of power.")

### 3. Strategic Analysis (전략 분석)
- **Grid vs. MGT:** Why did MGT run (or not run)? Relate to price/cost.
- **ESS Utilization:** Analyze charge/discharge patterns. (If ESS is unused, explain why).

### 4. Conclusion (결론)
- Final assessment of the operation efficiency.

**Language:** Professional Korean.
"""

class ExplanationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Explanation Agent Started ---")
        
        solution = state.get("solution_output")
        params = state.get("params")

        if not solution:
            state["explanation"] = "No optimization results found."
            return state

        # =========================================================
        # 1. 정밀 데이터 집계 (Python에서 미리 계산해서 LLM에 줌)
        # =========================================================
        try:
            total_cost = solution.get("Total_Cost", 0)
            
            # 시계열 데이터 추출
            time_steps = []
            p_grid_list = []
            p_mgt_list = []
            p_ess_dis_list = []
            p_ess_chg_list = []
            
            for t, val in solution.items():
                if isinstance(t, int) and isinstance(val, dict):
                    time_steps.append(t)
                    p_grid_list.append(val.get('P_grid', 0))
                    p_mgt_list.append(val.get('P_mgt', 0))
                    
                    # ESS는 없을 수도 있으므로 안전하게 get
                    p_ess_dis_list.append(val.get('P_discharge', 0)) # 방전
                    p_ess_chg_list.append(val.get('P_charge', 0))    # 충전

            # 총합 계산
            total_grid = sum(p_grid_list)
            total_mgt = sum(p_mgt_list)
            total_ess_dis = sum(p_ess_dis_list)
            total_ess_chg = sum(p_ess_chg_list)
            total_demand = total_grid + total_mgt + total_ess_dis # 충전은 수요가 아니므로 제외 (공급 관점)

            # 피크 타임 분석 (가장 전기를 많이 쓴 시간 찾기)
            # 공급 합 = Grid + MGT + Discharge
            total_supply_t = [g + m + d for g, m, d in zip(p_grid_list, p_mgt_list, p_ess_dis_list)]
            peak_load = max(total_supply_t)
            peak_idx = total_supply_t.index(peak_load)
            
            # 피크 시간대의 상황 (Time string 변환: 15분 단위)
            peak_hour = int(peak_idx / 4)
            peak_min = (peak_idx % 4) * 15
            peak_time_str = f"{peak_hour:02d}:{peak_min:02d}"
            
            # 피크 때 누가 얼마나 기여했나?
            peak_grid = p_grid_list[peak_idx]
            peak_mgt = p_mgt_list[peak_idx]
            peak_ess = p_ess_dis_list[peak_idx]

            # =========================================================
            # 2. LLM에게 던져줄 '팩트 시트' 작성
            # =========================================================
            summary_text = f"""
            [Optimization Data Fact Sheet]
            
            1. **Financials**
            - Total Daily Cost: {total_cost:,.0f} KRW
            
            2. **Energy Balance (Total MWh for 24h)**
            - Total Demand Met: {total_demand:.2f} MW (sum over time)
            - Grid Import: {total_grid:.2f} MW ({total_grid/total_demand*100:.1f}%)
            - MGT Generation: {total_mgt:.2f} MW ({total_mgt/total_demand*100:.1f}%)
            - ESS Discharge: {total_ess_dis:.2f} MW
            
            3. **Peak Load Analysis (Critical!)**
            - Peak Time: {peak_time_str}
            - Peak Load: {peak_load:.2f} MW
            - At Peak Time, sources were:
              -> Grid: {peak_grid:.2f} MW
              -> MGT: {peak_mgt:.2f} MW
              -> ESS Discharge: {peak_ess:.2f} MW
            
            4. **ESS Activity**
            - Total Charged: {total_ess_chg:.2f} MW
            - Total Discharged: {total_ess_dis:.2f} MW
            - (If these are 0, it means ESS was not used or not available).
            
            5. **Context**
            - If MGT generation is high, it implies Grid Price > MGT Cost.
            - If ESS Charge > 0, it implies price arbitrage was performed.
            """

            # 3. LLM 호출
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": summary_text},
                ],
                temperature=0.2, # 창의성 낮추고 분석력 높임
            )
            
            explanation = resp.choices[0].message.content
            state["explanation"] = explanation
            print("Explanation generated with detailed analysis.")
            
        except Exception as e:
            print(f"Explanation Error: {e}")
            import traceback
            traceback.print_exc()
            state["explanation"] = "Error generating detailed explanation."

        return state