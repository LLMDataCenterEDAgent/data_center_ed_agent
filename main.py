# main.py

import os
import matplotlib.pyplot as plt
from fpdf import FPDF, XPos, YPos
from workflow.graph import build_graph

# =========================================================
# 1. 결과 시각화 (인덱스 에러 수정됨)
# =========================================================
# main.py의 plot_results 함수를 이걸로 교체하세요

def plot_results(solution_data, params):
    if not solution_data: return

    times = range(params.time_steps)
    
    # 시간 라벨
    if params.timestamps:
        time_labels = [t.split(" ")[-1] for t in params.timestamps]
    else:
        time_labels = [f"{int(t/4):02d}:{int(t%4)*15:02d}" for t in times]

    # 데이터 추출
    p_grid = []
    p_g1 = []
    p_g2 = []
    p_ess_dis = []
    p_pv = []
    
    for t in times:
        val = solution_data.get(t, {})
        p_grid.append(val.get('P_grid', 0))
        p_g1.append(val.get('P_G1', 0))
        p_g2.append(val.get('P_G2', 0))
        p_ess_dis.append(val.get('P_dis_ESS1', 0))
        p_pv.append(val.get('P_PV', 0))

    # [핵심] 발전원별 데이터와 총합을 묶어서 관리
    sources = [
        {"label": "Grid",    "data": p_grid,    "total": sum(p_grid),    "color": "#1f77b4"}, # 파랑
        {"label": "G1",      "data": p_g1,      "total": sum(p_g1),      "color": "#d62728"}, # 빨강
        {"label": "G2",      "data": p_g2,      "total": sum(p_g2),      "color": "#9467bd"}, # 보라
        {"label": "ESS Dis", "data": p_ess_dis, "total": sum(p_ess_dis), "color": "#ff7f0e"}, # 주황
        {"label": "PV",      "data": p_pv,      "total": sum(p_pv),      "color": "#2ca02c"}  # 초록
    ]
    
    # [핵심] 총 발전량이 큰 순서대로 정렬 (내림차순)
    # stackplot은 리스트의 첫 번째 요소를 맨 아래에 그립니다.
    # 따라서 가장 많이 발전한(total이 큰) 순서대로 정렬하면 됩니다.
    sources.sort(key=lambda x: x['total'], reverse=True)
    
    # 정렬된 순서대로 데이터 추출
    y_arrays = [s['data'] for s in sources]
    labels = [s['label'] for s in sources]
    colors = [s['color'] for s in sources]

    # 그래프 그리기
    plt.figure(figsize=(12, 6))
    plt.stackplot(times, *y_arrays, labels=labels, colors=colors, alpha=0.85)
    
    plt.title("Optimization Result: Energy Mix (Sorted by Volume)", fontsize=15, fontweight='bold')
    plt.ylabel("Power (MW)", fontsize=12)
    plt.xlabel("Time", fontsize=12)
    
    # X축 간격 설정
    ticks = range(0, params.time_steps, 12)
    plt.xticks(ticks=ticks, labels=[time_labels[i] for i in ticks])
    plt.xlim(0, params.time_steps - 1)
    
    # 범례 순서도 그래프 쌓인 순서(위->아래)와 맞추려면 역순으로 표시하는 게 좋음
    handles, labels = plt.gca().get_legend_handles_labels()
    plt.legend(handles[::-1], labels[::-1], loc='upper left', title="Top to Bottom")
    
    plt.grid(True, linestyle='--', alpha=0.4)
    
    plt.savefig("optimization_result.png")
    print("[Graph] Saved to optimization_result.png (Sorted by Volume)")

# PDF 생성 함수는 기존 유지
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
# 3. 메인 실행
# =========================================================
# main.py의 실행 부분 (if __name__ == "__main__":)

if __name__ == "__main__":
    graph = build_graph()
    
    # 빈 상태로 시작 (ParsingAgent가 파일 로드 담당)
    initial_state = {"solution_output": None, "explanation": None}
    
    print("\n>> Running Workflow...")
    try:
        result = graph.invoke(initial_state)
        sol = result.get("solution_output")
        final_params = result.get("params") 
        
        if sol and final_params:
            print(f">> Success! Total Cost: {sol.get('Total_Cost', 0):,.0f}")
            print(f">> Simulation Steps: {final_params.time_steps} (Start: {final_params.timestamps[0]})")
            
            # 헤더
            print("-" * 115)
            print(f"{'Time':^8} | {'Grid':^8} | {'PV':^8} | {'G1':^8} | {'G2':^8} | {'ESS_Dis':^8} | {'Total':^8} | {'Net_Load':^8} | {'Diff':^6}")
            print("-" * 115)
            
            # [수정] 정확히 데이터 개수만큼만 반복 (60개면 60번)
            for t in range(final_params.time_steps):
                row = sol[t]
                
                # 공급 합계
                managed_supply = (
                    row.get('P_grid', 0) + row.get('P_G1', 0) + 
                    row.get('P_G2', 0) + row.get('P_dis_ESS1', 0)
                )
                
                # 목표 수요 (Net Load)
                target_demand = final_params.demand_profile[t]
                
                # PV
                p_pv = row.get('P_PV', 0)
                
                diff = managed_supply - target_demand
                
                # [핵심] 시간 라벨 (무조건 timestamps 사용)
                if final_params.timestamps:
                    # "2021-04-03 09:00" -> "09:00"
                    t_label = final_params.timestamps[t]
                    if " " in t_label: t_label = t_label.split(" ")[-1]
                else:
                    t_label = f"idx_{t}" # 만약 없으면 인덱스라도 출력
                
                print(f"{t_label:^8} | {row.get('P_grid',0):^8.1f} | {p_pv:^8.1f} | {row.get('P_G1',0):^8.1f} | {row.get('P_G2',0):^8.1f} | {row.get('P_dis_ESS1',0):^8.1f} | {managed_supply:^8.1f} | {target_demand:^8.1f} | {diff:^6.1f}")
            
            print("-" * 115)
            
            plot_results(sol, final_params)
            create_pdf_report(result.get("explanation"))
        else:
            print(">> No solution found.")
            
    except Exception as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()