# main.py

import os
import matplotlib.pyplot as plt
from fpdf import FPDF, XPos, YPos
from workflow.graph import build_graph

# =========================================================
# 1. 결과 시각화 (동적 발전원 처리 + 자동 정렬 + 색상 지정)
# =========================================================
# main.py의 plot_results 함수를 이걸로 교체하세요

# main.py의 plot_results 함수를 이걸로 교체하세요

def plot_results(solution_data, params):
    if not solution_data: return

    T = params.time_steps
    times = range(T)
    
    # 시간 라벨
    if params.timestamps and len(params.timestamps) == T:
        time_labels = [t.split(" ")[-1] for t in params.timestamps]
    else:
        time_labels = [f"{int(t/4):02d}:{int(t%4)*15:02d}" for t in times]

    # 데이터 추출
    p_grid = []
    p_pv = []
    p_ess_dis = []
    
    # 발전기 데이터 (동적)
    gen_data = {g: [] for g in params.generators}

    for t in times:
        val = solution_data.get(t, {})
        p_grid.append(val.get('P_grid', 0))
        p_pv.append(val.get('P_PV', 0))
        p_ess_dis.append(val.get('P_dis_ESS1', val.get('P_discharge', 0)))
        
        for g in params.generators:
            gen_data[g].append(val.get(f'P_{g}', val.get(g, 0)))

    # ---------------------------------------------------------
    # [핵심] 색상 및 순서 전략
    # ---------------------------------------------------------
    color_map = {
        "SMR1": "#9467bd",    # 보라색 (가장 무거운 기저부하)
        "PV":   "#2ca02c",    # 초록색 (재생에너지)
        "GT1":  "#d62728",    # 빨간색 (변동성 큼)
        "GT2":  "#ff7f0e",    # 주황색 (GT1과 확연히 구분되게 변경!)
        "ESS Dis": "#8c564b", # 갈색 (보조)
        "Grid": "#1f77b4"     # 파란색 (최후의 수단)
    }

    sources = []

    # 1. SMR (무조건 맨 아래 고정)
    if "SMR1" in gen_data:
        sources.append({
            "label": "SMR1 (Base)", 
            "data": gen_data["SMR1"], 
            "total": sum(gen_data["SMR1"]), 
            "color": color_map["SMR1"]
        })
        del gen_data["SMR1"]

    # 2. PV (그 다음)
    sources.append({"label": "PV", "data": p_pv, "total": sum(p_pv), "color": color_map["PV"]})

    # 3. GT1, GT2 (그 위에 쌓아서 변동성 보여주기)
    # GT들이 서로 섞이지 않고 SMR 위에 층층이 쌓이도록 처리
    if "GT1" in gen_data:
        sources.append({"label": "GT1", "data": gen_data["GT1"], "total": sum(gen_data["GT1"]), "color": color_map["GT1"]})
        del gen_data["GT1"]
        
    if "GT2" in gen_data:
        sources.append({"label": "GT2", "data": gen_data["GT2"], "total": sum(gen_data["GT2"]), "color": color_map["GT2"]})
        del gen_data["GT2"]

    # 4. 나머지 (ESS, Grid 등 - 자동 정렬)
    temp_sources = []
    temp_sources.append({"label": "Grid", "data": p_grid, "total": sum(p_grid), "color": color_map["Grid"]})
    temp_sources.append({"label": "ESS Dis", "data": p_ess_dis, "total": sum(p_ess_dis), "color": color_map["ESS Dis"]})
    
    # 혹시 남은 발전기가 있다면 추가
    for g_name, data in gen_data.items():
        temp_sources.append({"label": g_name, "data": data, "total": sum(data), "color": "#7f7f7f"})
    
    # 나머지는 발전량 순서대로
    temp_sources.sort(key=lambda x: x['total'], reverse=True)
    sources.extend(temp_sources)

    # ---------------------------------------------------------
    
    y_arrays = [s['data'] for s in sources]
    labels = [s['label'] for s in sources]
    colors = [s['color'] for s in sources]

    plt.figure(figsize=(12, 6))
    plt.stackplot(times, *y_arrays, labels=labels, colors=colors, alpha=0.85)
    
    plt.title("Optimization Result: Energy Mix (SMR Base + GT Variable)", fontsize=15, fontweight='bold')
    plt.ylabel("Power (MW)", fontsize=12)
    plt.xlabel("Time", fontsize=12)
    
    ticks = range(0, T, 12)
    plt.xticks(ticks=ticks, labels=[time_labels[i] for i in ticks])
    plt.xlim(0, T-1)
    
    # 범례 역순
    handles, labels = plt.gca().get_legend_handles_labels()
    plt.legend(handles[::-1], labels[::-1], loc='upper left', title="Stack Order")
    
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.savefig("optimization_result.png")
    print("[Graph] Saved to optimization_result.png (GTs Highlighted)")
    
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
    print(f"[PDF] Saved to {filename}")

# =========================================================
# 3. 메인 실행 (발전기 자동 탐지 기능 추가)
# =========================================================
if __name__ == "__main__":
    graph = build_graph()
    initial_state = {"solution_output": None, "explanation": None}
    
    print("\n>> Running Workflow...")
    try:
        result = graph.invoke(initial_state)
        sol = result.get("solution_output")
        final_params = result.get("params") 
        
        if sol and final_params:
            print(f">> Success! Total Cost: {sol.get('Total_Cost', 0):,.0f}")
            
            # [핵심] 발전기 이름 자동 추출 (GT1, GT2, SMR1 ...)
            gen_names = list(final_params.generators.keys())
            
            # 헤더 생성
            gen_header_str = " | ".join([f"{g:^8}" for g in gen_names])
            total_len = 80 + len(gen_names) * 11
            
            print("-" * total_len)
            print(f"{'Time':^8} | {'Grid':^8} | {'PV':^8} | {gen_header_str} | {'ESS_Dis':^8} | {'Total':^8} | {'Net_Load':^8} | {'Diff':^6}")
            print("-" * total_len)
            
            for t in range(final_params.time_steps):
                row = sol[t]
                
                # 1. 값 추출
                p_grid = row.get('P_grid', 0)
                p_pv = row.get('P_PV', 0)
                p_ess_dis = row.get('P_dis_ESS1', row.get('P_discharge', 0))
                
                # 2. 발전기 합계 및 문자열 생성
                gen_vals = []
                p_gen_sum = 0
                for g in gen_names:
                    val = row.get(f'P_{g}', row.get(g, 0))
                    gen_vals.append(val)
                    p_gen_sum += val
                
                gen_val_str = " | ".join([f"{v:^8.1f}" for v in gen_vals])
                
                # 3. 총 공급 및 오차
                # Total = Grid + PV + Gen_Sum + ESS_Dis (Net_Load 비교를 위해 PV 포함 여부 주의)
                # 여기선 Display용 Total Supply를 보여줌
                # Net Load = Demand - PV 이므로,
                # Managed Supply (Grid+Gen+ESS)가 Net Load와 같아야 함.
                
                managed_supply = p_grid + p_gen_sum + p_ess_dis
                target_demand = final_params.demand_profile[t] # Net Load
                
                diff = managed_supply - target_demand
                
                # 4. 시간 라벨
                if final_params.timestamps:
                    t_label = final_params.timestamps[t].split(" ")[-1]
                else:
                    t_label = f"{t}"
                
                # 출력
                print(f"{t_label:^8} | {p_grid:^8.1f} | {p_pv:^8.1f} | {gen_val_str} | {p_ess_dis:^8.1f} | {managed_supply:^8.1f} | {target_demand:^8.1f} | {diff:^6.1f}")
            
            print("-" * total_len)
            
            plot_results(sol, final_params)
            create_pdf_report(result.get("explanation"))
        else:
            print(">> No solution found.")
            
    except Exception as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()