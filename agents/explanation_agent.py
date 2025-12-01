# agents/explanation_agent.py

from openai import OpenAI
from state.schemas import EDParams, EDSolution

client = OpenAI()

SYSTEM_PROMPT = """
You are an ED (Economic Dispatch) expert. 
Always produce BOTH:
1) A concise basic summary of numeric results, AND
2) A detailed engineering explanation.

The output MUST have the following structure exactly:

------ BASIC SUMMARY ------
(여기에 기본 요약: 발전기 출력, 총 비용, 상태 포함)

------ ENGINEERING ANALYSIS ------
(여기에 slack, λ, 수요제약, 각 발전기 상태, 해석)

Use clear Korean. 
Never omit the BASIC SUMMARY section.
Never merge the two sections.
"""


def explain_solution(params: EDParams, sol: EDSolution) -> str:

    P1 = sol.Pg["G1"]
    P2 = sol.Pg["G2"]

    F1 = sol.fuel_costs["G1"]
    F2 = sol.fuel_costs["G2"]

    lam = sol.lambda_val
    bal = sol.balance_violation

    s1 = sol.slacks["G1"]
    s2 = sol.slacks["G2"]

    user_prompt = f"""
다음은 발전기 2기 경제급전(ED)의 해입니다.

[Numeric values]
- P1 = {P1:.2f}
- P2 = {P2:.2f}
- Total cost = {sol.cost:.2f}
- Status = {sol.note}

[Fuel costs]
- F1 = {F1:.4f}
- F2 = {F2:.4f}

[Slack]
- G1 slack: lower={s1['lower']:.2f}, upper={s1['upper']:.2f}
- G2 slack: lower={s2['lower']:.2f}, upper={s2['upper']:.2f}

[Demand check]
- P1+P2-D = {bal:.6f}

[Lambda]
- λ = {lam}

위 값들을 기반으로 BASIC SUMMARY와 ENGINEERING ANALYSIS 두 가지 섹션으로 나누어 설명해줘.
"""

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content
