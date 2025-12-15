# main.py

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from fpdf import FPDF, XPos, YPos
from workflow.graph import build_graph

# =========================================================
# 1. 결과 시각화 함수 (기존 유지)
# =========================================================
def plot_results(solution_data, params):
    if not solution_data: return

    T = params.time_steps
    times = range(T)
    
    if params.timestamps and len(params.timestamps) == T:
        time_labels = [t.split(" ")[-1] for t in params.timestamps]
    else:
        time_labels = [f"{int(t/4):02d}:{int(t%4)*15:02d}" for t in times]

    p_grid, p_pv = [], []
    gen_names = list(params.generators.keys())
    ess_names = list(params.ess.keys()) if params.ess else []
    
    gen_data = {g: [] for g in gen_names}
    ess_data = {e: [] for e in ess_names}

    for t in times:
        val = solution_data.get(t, {})
        p_grid.append(val.get('P_grid', 0))
        p_pv.append(val.get('P_PV', 0))
        for g in gen_names:
            gen_data[g].append(val.get(f'P_{g}', val.get(g, 0)))
        for e in ess_names:
            ess_data[e].append(val.get(f'P_dis_{e}', 0))

    sources = []
    sources.append({"label": "PV", "data": p_pv, "total": sum(p_pv), "priority": 0, "color": "#2ca02c"})

    reds = ["#d62728", "#ff7f0e", "#e377c2", "#bcbd22", "#8c564b"]
    for i, g in enumerate(gen_names):
        name_upper = g.upper()
        if "SMR" in name_upper or "NUC" in name_upper:
            priority, color = 1, "#9467bd"
        else:
            priority, color = 2, reds[i % len(reds)]
        sources.append({"label": g, "data": gen_data[g], "total": sum(gen_data[g]), "priority": priority, "color": color})

    browns = ["#8B4513", "#A0522D", "#CD853F"]
    for i, e in enumerate(ess_names):
        sources.append({"label": f"{e} Dis", "data": ess_data[e], "total": sum(ess_data[e]), "priority": 3, "color": browns[i % len(browns)]})

    sources.append({"label": "Grid", "data": p_grid, "total": sum(p_grid), "priority": 4, "color": "#1f77b4"})
    sources.sort(key=lambda x: (x['priority'], -x['total']))

    y_arrays = [s['data'] for s in sources if s['total'] > 0.1]
    labels = [s['label'] for s in sources if s['total'] > 0.1]
    colors = [s['color'] for s in sources if s['total'] > 0.1]

    plt.figure(figsize=(12, 6))
    plt.stackplot(times, *y_arrays, labels=labels, colors=colors, alpha=0.9, edgecolor='white', linewidth=0.5)
    
    plt.title(f"Optimization Result: Merit Order Stack", fontsize=15, fontweight='bold')
    plt.ylabel("Power (MW)", fontsize=12)
    plt.xlabel("Time", fontsize=12)
    
    ticks = range(0, T, 12)
    plt.xticks(ticks=ticks, labels=[time_labels[i] for i in ticks])
    plt.xlim(0, T-1)
    
    handles, labels = plt.gca().get_legend_handles_labels()
    plt.legend(handles[::-1], labels[::-1], loc='upper left', title="Cost Order")
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.savefig("optimization_result.png")
    print(f"[Graph] Saved to optimization_result.png")

# =========================================================
# 2. PDF 리포트 생성 함수 (소수점 포함 2단 레이아웃)
# =========================================================
def create_pdf_report(explanation_text, solution_data=None, params=None, image_path="optimization_result.png", filename="Final_Report.pdf"):
    pdf = FPDF()
    
    font_path = r'C:\Windows\Fonts\malgun.ttf'
    font_name = 'Arial'
    if os.path.exists(font_path):
        try: 
            pdf.add_font('KoreanFont', '', fname=font_path)
            font_name = 'KoreanFont'
        except: 
            pass
    
    # -----------------------------------------------------
    # Page 1: 요약 및 그래프
    # -----------------------------------------------------
    pdf.add_page()
    pdf.set_font(font_name, '', 16)
    pdf.cell(0, 10, "AI Data Center Energy Optimization Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(5)
    
    if os.path.exists(image_path): 
        pdf.image(image_path, x=15, w=180)
        pdf.ln(5)
    
    pdf.set_font(font_name, '', 10)
    try: 
        pdf.multi_cell(0, 6, explanation_text if explanation_text else "No content.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    except: 
        pdf.multi_cell(0, 6, "Text error.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # -----------------------------------------------------
    # Page 2: 상세 데이터 테이블 (소수점 포함, 2단)
    # -----------------------------------------------------
    if solution_data and params:
        pdf.add_page()
        pdf.set_font(font_name, '', 12)
        pdf.cell(0, 10, "Detailed Simulation Data (24h)", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.ln(2)
        
        # 1. 헤더 준비
        gen_names = list(params.generators.keys())
        ess_names = list(params.ess.keys()) if params.ess else []
        headers = ["Time", "Grid", "PV"] + gen_names + [f"{e}" for e in ess_names] + ["Total", "Diff"]
        
        # 2. 너비 및 높이 설정
        page_width = 190
        col_gap = 4      
        block_width = (page_width - col_gap) / 2
        
        num_cols = len(headers)
        col_width = block_width / num_cols
        row_height = 4 
        
        # 3. 데이터 분할
        total_steps = params.time_steps
        mid_point = (total_steps + 1) // 2
        
        # --- 내부 함수: 테이블 블록 그리기 ---
        def draw_table_block(start_idx, end_idx, x_start, y_start):
            # 헤더
            pdf.set_xy(x_start, y_start)
            pdf.set_font(font_name, '', 5) # 헤더 폰트 작게
            pdf.set_fill_color(220, 230, 255)
            
            for h in headers:
                pdf.cell(col_width, row_height, h, border=1, align='C', fill=True)
            
            current_y = y_start + row_height
            
            # 데이터
            pdf.set_font(font_name, '', 4.5) # [핵심] 폰트를 4.5pt로 줄여서 소수점 공간 확보
            for t in range(start_idx, end_idx):
                if t >= total_steps: break
                
                pdf.set_xy(x_start, current_y)
                row = solution_data[t]
                
                # 값 추출 (소수점 1자리 복구)
                vals = []
                t_label = params.timestamps[t].split(" ")[-1][:5] if params.timestamps else f"{t}"
                vals.append(t_label)
                
                # Grid, PV
                vals.append(f"{row.get('P_grid',0):.1f}")
                vals.append(f"{row.get('P_PV',0):.1f}")
                
                # Gens
                p_gen_sum = 0
                for g in gen_names:
                    val = row.get(f'P_{g}', row.get(g, 0))
                    vals.append(f"{val:.1f}")
                    p_gen_sum += val
                
                # ESS
                p_ess_sum = 0
                for e in ess_names:
                    val = row.get(f'P_dis_{e}', 0)
                    vals.append(f"{val:.1f}")
                    p_ess_sum += val
                
                # Total & Diff
                managed = row.get('P_grid',0) + p_gen_sum + p_ess_sum
                target = params.demand_profile[t]
                diff = managed - target
                vals.append(f"{managed:.1f}")
                vals.append(f"{diff:.1f}")
                
                # 행 그리기
                for v in vals:
                    pdf.cell(col_width, row_height, v, border=1, align='C')
                
                current_y += row_height

        # 4. 실제 그리기
        start_y = pdf.get_y()
        draw_table_block(0, mid_point, 10, start_y)
        draw_table_block(mid_point, total_steps, 10 + block_width + col_gap, start_y)

    pdf.output(filename)
    print(f"[PDF] Saved to {filename} (2-Column Layout with Decimals)")

# =========================================================
# 3. 메인 실행 (CSV 데이터 연동)
# =========================================================
if __name__ == "__main__":
    graph = build_graph()
    
    # -----------------------------------------------------
    # [Step 1] gtfuel.csv 읽어서 Min/Max 추출
    # -----------------------------------------------------
    gt_min = 40.0   # 기본값
    gt_max = 120.0  # 기본값
    csv_file = "gtfuel.csv"

    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            
            target_col = None
            for col in df.columns:
                if "power" in col and "mw" in col:
                    target_col = col
                    break
            
            if target_col:
                gt_min = float(df[target_col].min())
                gt_max = float(df[target_col].max())
                print(f">> [System] Fuel CSV Loaded. GT Range: {gt_min:.2f} ~ {gt_max:.2f} MW")
        except:
            pass

    # -----------------------------------------------------
    # [Step 2] 추출한 값을 f-string으로 프롬프트에 삽입
    # -----------------------------------------------------
    user_request = f"""
    가스터빈(GT) 2대는 비용이 85.0이고 (Grid 50보다 비쌈, 150보다 쌈),
    최소 {gt_min}MW, 최대 {gt_max}MW 범위로 운전해.
    
    SMR 1대는 비용이 5.0으로 아주 싸고, 
    최소 100MW, 최대 121MW야.
    
    ESS는 1대(300MWh, 80MW) 있어.
    """
    
    print(f">> [Generated Prompt]\n{user_request.strip()}\n")
    
    initial_state = {
        "problem_text": user_request, 
        "solution_output": None, 
        "explanation": None
    }
    
    print(">> Running Workflow...")
    try:
        result = graph.invoke(initial_state)
        sol = result.get("solution_output")
        final_params = result.get("params") 
        
        if sol and final_params:
            print(f">> Success! Total Cost: {sol.get('Total_Cost', 0):,.0f}")
            
            # 터미널 출력용 헤더 (터미널은 공간이 넓으니 소수점 넉넉하게)
            gen_names = list(final_params.generators.keys())
            ess_names = list(final_params.ess.keys()) if final_params.ess else []
            headers = ["Time", "Grid", "PV"] + gen_names + [f"{e}_Dis" for e in ess_names] + ["Total", "Net_Load", "Diff"]
            header_fmt = " | ".join([f"{h:^8}" for h in headers])
            
            line_len = len(header_fmt) + 5
            print("-" * line_len)
            print(header_fmt)
            print("-" * line_len)
            
            for t in range(final_params.time_steps):
                row = sol[t]
                vals = []
                t_label = final_params.timestamps[t].split(" ")[-1] if final_params.timestamps else f"{t}"
                vals.append(t_label)
                
                p_grid = row.get('P_grid', 0)
                p_pv = row.get('P_PV', 0)
                vals.append(p_grid)
                vals.append(p_pv)
                
                p_gen_sum = 0
                for g in gen_names:
                    val = row.get(f'P_{g}', row.get(g, 0))
                    vals.append(val)
                    p_gen_sum += val
                    
                p_ess_sum = 0
                for e in ess_names:
                    val = row.get(f'P_dis_{e}', 0)
                    vals.append(val)
                    p_ess_sum += val
                
                managed_supply = p_grid + p_gen_sum + p_ess_sum
                target_demand = final_params.demand_profile[t]
                diff = managed_supply - target_demand
                
                vals.append(managed_supply)
                vals.append(target_demand)
                vals.append(diff)
                
                row_str = " | ".join([f"{v:^8}" if isinstance(v, str) else f"{v:^8.1f}" for v in vals])
                print(row_str)
            
            print("-" * line_len)
            
            plot_results(sol, final_params)
            
            create_pdf_report(
                result.get("explanation"), 
                solution_data=sol, 
                params=final_params
            )
        else:
            print(">> No solution found.")
            
    except Exception as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()