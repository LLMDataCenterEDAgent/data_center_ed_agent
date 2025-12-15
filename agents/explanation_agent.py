# agents/explanation_agent.py

from openai import OpenAI
from state.base_state import AgentState

client = OpenAI()

SYSTEM_PROMPT = """
You are an expert 'AI Data Center Energy Consultant'.
Based on the optimization results, provide a professional Executive Summary in Korean.
Focus on:
1. Total Cost & Efficiency.
2. Energy Mix (Grid vs Self-generation vs ESS).
3. How the system adapted to the season/time (Peak shaving).
Use specific numbers from the data provided.
"""

class ExplanationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Explanation Agent Started ---")
        
        sol = state.get("solution_output")
        params = state.get("params") 

        if not sol or not params:
            state["explanation"] = "데이터 부족."
            return state

        try:
            total_cost = sol.get("Total_Cost", 0)
            
            total_grid = 0
            total_pv = 0
            total_gen = 0
            total_ess_dis = 0
            
            gen_names = list(params.generators.keys())
            ess_names = list(params.ess.keys()) if params.ess else []
            
            # 통계 집계
            for t, val in sol.items():
                if isinstance(t, int) and isinstance(val, dict):
                    total_grid += val.get('P_grid', 0)
                    total_pv += val.get('P_PV', 0)
                    for g in gen_names:
                        total_gen += val.get(f'P_{g}', 0)
                    for e in ess_names:
                        total_ess_dis += val.get(f'P_dis_{e}', 0)

            total_supply = total_grid + total_pv + total_gen + total_ess_dis
            
            # LLM 입력
            summary_input = f"""
            [Result Data]
            - Total Cost: {total_cost:,.0f} KRW
            - Total Supply: {total_supply:,.1f} MW
            - Grid Import: {total_grid:,.1f} MW
            - PV Generation: {total_pv:,.1f} MW
            - Generators ({', '.join(gen_names)}): {total_gen:,.1f} MW
            - ESS Discharge: {total_ess_dis:,.1f} MW
            - Season/Month: {params.grid_price_profile[0] if params.grid_price_profile else 'Unknown'}
            """

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
            print(">> Explanation Generated.")
            
        except Exception as e:
            print(f"Explanation Error: {e}")
            state["explanation"] = "Error."

        return state