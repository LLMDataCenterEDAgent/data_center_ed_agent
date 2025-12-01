# agents/explanation_agent.py

from openai import OpenAI
from state.schemas import EDParams, EDSolution

client = OpenAI()

SYSTEM_PROMPT = """
You are an assistant that explains economic dispatch (ED) results
in clear Korean for an engineering student. Be concise but include
all key numbers.
"""

def explain_solution(params: EDParams, sol: EDSolution) -> str:
    P1 = sol.Pg["G1"]
    P2 = sol.Pg["G2"]
    F1 = sol.fuel_costs.get("G1") if sol.fuel_costs else None
    F2 = sol.fuel_costs.get("G2") if sol.fuel_costs else None
    lam = sol.lambda_val
    bal = sol.balance_violation
    s1 = sol.slacks["G1"] if sol.slacks else None
    s2 = sol.slacks["G2"] if sol.slacks else None

    user_prompt = f"""
다음은 2-발전기 경제급전(ED) 문제의 해입니다.

[입력 요약]
- 총 수요(D): {params.demand:.2f} MW
- 발전기1 제약: [{params.generators['G1'].p_min:.2f}, {params.generators['G1'].p_max:.2f}] MW
- 발전기2 제약: [{params.generators['G2'].p_min:.2f}, {params.generators['G2'].p_max:.2f}] MW

[최적 출력]
- P1* = {P1:.2f} MW
- P2* = {P2:.2f} MW

[비용]
- 발전기1 연료비 F1 = {F1:.4f}
- 발전기2 연료비 F2 = {F2:.4f}
- 총 비용 F = F1 + F2 = {sol.cost:.4f}

[한계비용 및 수요 제약]
- 시스템 한계비용 λ ≈ {lam:.4f}  (bounds에 걸리지 않은 발전기의 MC 기준)
- 수요 제약 체크: P1 + P2 - D = {bal:.6f}  → 0에 매우 가까우면 수요 제약이 잘 만족됨.

[출력 제약 slack]
- 발전기1: lower slack = P1 - P1_min = {s1['lower']:.4f}, upper slack = P1_max - P1 = {s1['upper']:.4f}
- 발전기2: lower slack = P2 - P2_min = {s2['lower']:.4f}, upper slack = P2_max - P2 = {s2['upper']:.4f}

위 정보를 바탕으로, 
1) 어떤 발전기가 상한/하한에 근접해 있는지, 
2) λ와 각 발전기 한계비용이 어떻게 정렬되는지,
3) 수요 제약이 얼마나 잘 맞는지

를 한국어로 짧게 요약해서 설명해줘.
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
