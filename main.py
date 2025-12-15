# main.py

import os
import matplotlib.pyplot as plt
import matplotlib.cm as cm # 컬러맵 사용
from fpdf import FPDF, XPos, YPos
from workflow.graph import build_graph

# =========================================================
# 1. 결과 시각화 (완전 동적: 발전기 N개 + ESS N개)
# =========================================================
def plot_results(solution_data, params):
    if not solution_data: return

    T = params.time_steps
    times = range(T)
    
    # 시간 라벨
    if params.timestamps and len(params.timestamps) == T:
        time_labels = [t.split(" ")[-1] for t in params.timestamps]
    else:
        time_labels = [f"{int(t/4):02d}:{int(t%4)*15:02d}" for t in times]

    # ---------------------------------------------------------
    # 1. 데이터 수집 (발전기 & ESS 자동 탐지)
    # ---------------------------------------------------------
    p_grid = []
    p_pv = []
    
    # 동적 리스트
    gen_names = list(params.generators.keys())
    ess_names = list(params.ess.keys()) if params.ess else []
    
    gen_data = {g: [] for g in gen_names}
    ess_data = {e: [] for e in ess_names} # ESS 방전량

    for t in times:
        val = solution_data.get(t, {})
        p_grid.append(val.get('P_grid', 0))
        p_pv.append(val.get('P_PV', 0))
        
        # 발전기 데이터 수집
        for g in gen_names:
            gen_data[g].append(val.get(f'P_{g}', val.get(g, 0)))
            
        # ESS 방전 데이터 수집 (여러 대일 경우 대비)
        for e in ess_names:
            # SolverAgent는 P_dis_ESS1 형태로 저장함
            ess_data[e].append(val.get(f'P_dis_{e}', 0))

    # ---------------------------------------------------------
    # 2. 스택 순서 및 색상 결정
    # ---------------------------------------------------------
    sources = []
    
    # (1) PV (무조건 바닥)
    sources.append({"label": "PV", "data": p_pv, "total": sum(p_pv), "priority": 0, "color": "#2ca02c"}) # 초록

    # (2) SMR / Nuclear (기저부하)
    for g in gen_names:
        if "SMR" in g.upper() or "NUC" in g.upper():
            sources.append({"label": g, "data": gen_data[g], "total": sum(gen_data[g]), "priority": 1, "color": "#9467bd"}) # 보라

    # (3) 일반 발전기 (GT 등) - 발전량 순 자동 색상
    gt_list = [g for g in gen_names if "SMR" not in g.upper()]
    # 색상 팔레트 (붉은/주황 계열)
    reds = ["#d62728", "#ff7f0e", "#e377c2", "#bcbd22", "#8c564b"]
    
    for i, g in enumerate(gt_list):
        color = reds[i % len(reds)]
        sources.append({"label": g, "data": gen_data[g], "total": sum(gen_data[g]), "priority": 2, "color": color})

    # (4) ESS 방전 (여러 대일 경우)
    # ESS 색상 팔레트 (갈색 계열)
    browns = ["#8B4513", "#A0522D", "#CD853F"]
    for i, e in enumerate(ess_names):
        color = browns[i % len(browns)]
        sources.append({"label": f"{e} Dis", "data": ess_data[e], "total": sum(ess_data[e]), "priority": 3, "color": color})

    # (5) Grid (최상단)
    sources.append({"label": "Grid", "data": p_grid, "total": sum(p_grid), "priority": 4, "color": "#1f77b4"}) # 파랑

    # 정렬: Priority -> Total Volume
    sources.sort(key=lambda x: (x['priority'], -x['total']))

    # ---------------------------------------------------------
    
    y_arrays = [s['data'] for s in sources if s['total'] > 0.1]
    labels = [s['label'] for s in sources if s['total'] > 0.1]
    colors = [s['color'] for s in sources if s['total'] > 0.1]

    plt.figure(figsize=(12, 6))
    plt.stackplot(times, *y_arrays, labels=labels, colors=colors, alpha=0.9, edgecolor='white', linewidth=0.5)
    
    title_str = f"Optimization: {len(gen_names)} Gens + {len(ess_names)} ESS"
    plt.title(title_str, fontsize=15, fontweight='bold')
    plt.ylabel("Power (MW)", fontsize=12)
    plt.xlabel("Time", fontsize=12)
    
    ticks = range(0, T, 12)
    plt.xticks(ticks=ticks, labels=[time_labels[i] for i in ticks])
    plt.xlim(0, T-1)
    
    handles, labels = plt.gca().get_legend_handles_labels()
    plt.legend(handles[::-1], labels[::-1], loc='upper left', title="Layer Order")
    
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.savefig("optimization_result.png")
    print(f"[Graph] Saved. (Includes {len(ess_names)} ESS units)")

# PDF 생성 함수
def create_pdf_report(explanation_text, image_path="optimization_result.png", filename="Final_Report.pdf"):
    pdf = FPDF()
    pdf.add_page()
    font_path = r'C:\Windows\Fonts\malgun.ttf'
    if os.path.exists(font_path):
        try: pdf.add_font('KoreanFont', '', fname=font_path); pdf.set_font('KoreanFont', '', 11)
        except: pdf.set_font('Arial', '', 11)
    else: pdf.set_font('Arial', '', 11)
    
    pdf.set_font_size(16)
    pdf.cell(0, 10, "AI Data Center Energy Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(5)
    if os.path.exists(image_path): pdf.image(image_path, x=15, w=180); pdf.ln(5)
    pdf.set_font_size(10)
    try: pdf.multi_cell(0, 6, explanation_text if explanation_text else "No content.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    except: pdf.multi_cell(0, 6, "Text error.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.output(filename)
    print(f"[PDF] Saved.")

# =========================================================
# 3. 메인 실행 (사용자 자연어 입력)
# =========================================================
if __name__ == "__main__":
    graph = build_graph()
    
    # -----------------------------------------------------
    # [사용자 입력] 여기서 마음대로 시나리오를 바꾸세요!
    # -----------------------------------------------------
    user_request = """
        가스터빈(GT)은 2대가 있고, 최소 85, 최대 120MW야.
        GT의 비용은 2차 함수 형태인데, 
        a는 0.005, b는 10.0, c는 500.0을 사용해줘. (P^2 단위 비용)
        SMR 1대는 기존처럼 비용은 0.002로 아주 싸.
        ESS는 1대(ESS1) 있는데 용량 160MWh, 출력 40MW야.
        """
    # -----------------------------------------------------
    
    initial_state = {
        "problem_text": user_request, 
        "solution_output": None, 
        "explanation": None
    }
    
    print("\n>> Running Workflow...")
    try:
        result = graph.invoke(initial_state)
        sol = result.get("solution_output")
        final_params = result.get("params") 
        
        if sol and final_params:
            print(f">> Success! Total Cost: {sol.get('Total_Cost', 0):,.0f}")
            
            # 동적 헤더 생성 (Gen + ESS)
            gen_names = list(final_params.generators.keys())
            ess_names = list(final_params.ess.keys()) if final_params.ess else []
            
            # [수정됨] 이전에 에러나던 중복 코드를 제거하고 깔끔하게 정리했습니다.
            headers = ["Time", "Grid", "PV"] + gen_names + [f"{e}_Dis" for e in ess_names] + ["Total", "Net_Load", "Diff"]
            header_fmt = " | ".join([f"{h:^8}" for h in headers])
            
            line_len = len(header_fmt) + 5
            print("-" * line_len)
            print(header_fmt)
            print("-" * line_len)
            
            for t in range(final_params.time_steps):
                row = sol[t]
                
                # 값 가져오기
                vals = []
                # Time
                t_label = final_params.timestamps[t].split(" ")[-1] if final_params.timestamps else f"{t}"
                vals.append(t_label)
                
                # Grid, PV
                p_grid = row.get('P_grid', 0)
                p_pv = row.get('P_PV', 0)
                vals.append(p_grid)
                vals.append(p_pv)
                
                # Gens
                p_gen_sum = 0
                for g in gen_names:
                    val = row.get(f'P_{g}', row.get(g, 0))
                    vals.append(val)
                    p_gen_sum += val
                    
                # ESSs
                p_ess_sum = 0
                for e in ess_names:
                    val = row.get(f'P_dis_{e}', 0)
                    vals.append(val)
                    p_ess_sum += val
                
                # Totals
                managed_supply = p_grid + p_gen_sum + p_ess_sum
                target_demand = final_params.demand_profile[t]
                diff = managed_supply - target_demand
                
                vals.append(managed_supply)
                vals.append(target_demand)
                vals.append(diff)
                
                # 출력 포맷 (문자열은 그대로, 숫자는 소수점 1자리)
                row_str = " | ".join([f"{v:^8}" if isinstance(v, str) else f"{v:^8.1f}" for v in vals])
                print(row_str)
            
            print("-" * line_len)
            
            plot_results(sol, final_params)
            create_pdf_report(result.get("explanation"))
        else:
            print(">> No solution found.")
            
    except Exception as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()