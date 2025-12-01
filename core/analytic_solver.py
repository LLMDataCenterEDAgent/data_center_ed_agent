# core/analytic_solver.py

from state.schemas import EDParams, EDSolution

def analytic_solve_two_gen(params: EDParams) -> EDSolution:
    g1 = params.generators["G1"]
    g2 = params.generators["G2"]
    D = params.demand

    a1, b1, c1 = g1.a, g1.b, g1.c
    a2, b2, c2 = g2.a, g2.b, g2.c

    # 1) 등식 제약 P2 = D - P1 사용해서 F(P1)를 2차식으로 만들고 미분 → 무제약 최적 P1*
    A = a1 + a2
    B = b1 - 2 * a2 * D - b2
    P1_star = -B / (2 * A)

    # 2) 발전기 출력 bounds 적용
    P1 = min(max(P1_star, g1.p_min), g1.p_max)
    P2 = D - P1

    # 3) 비용 계산
    F1 = a1 * P1**2 + b1 * P1 + c1
    F2 = a2 * P2**2 + b2 * P2 + c2
    cost = F1 + F2

    # 4) 한계비용(MC) 계산
    MC1 = 2 * a1 * P1 + b1
    MC2 = 2 * a2 * P2 + b2

    # 5) λ (system marginal cost) 추정
    #    - bounds에 걸려있지 않은 발전기의 MC를 λ로 사용
    #    - 둘 다 interior면 두 MC의 평균
    #    - 둘 다 bound면 None (정의 애매)
    interior_mcs = []

    def is_interior(P, g):
        return (P > g.p_min + 1e-6) and (P < g.p_max - 1e-6)

    if is_interior(P1, g1):
        interior_mcs.append(MC1)
    if is_interior(P2, g2):
        interior_mcs.append(MC2)

    if len(interior_mcs) == 1:
        lambda_val = interior_mcs[0]
    elif len(interior_mcs) == 2:
        lambda_val = sum(interior_mcs) / 2.0
    else:
        lambda_val = None  # 둘 다 bound에 걸린 경우 등

    # 6) 수요 제약 체크: (P1+P2) - D (0에 가까우면 OK)
    balance_violation = (P1 + P2) - D

    # 7) 출력 제약 slack 계산
    slacks = {
        "G1": {
            "lower": P1 - g1.p_min,
            "upper": g1.p_max - P1,
        },
        "G2": {
            "lower": P2 - g2.p_min,
            "upper": g2.p_max - P2,
        },
    }

    fuel_costs = {"G1": F1, "G2": F2}

    note = "analytic optimum (with MC, lambda, slacks)"

    return EDSolution(
        Pg={"G1": P1, "G2": P2},
        cost=cost,
        note=note,
        lambda_val=lambda_val,
        fuel_costs=fuel_costs,
        balance_violation=balance_violation,
        slacks=slacks,
    )
