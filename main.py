# main.py
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
from workflow.graph import build_graph
from fpdf import FPDF

# 1. 데이터 로드 함수 (Data Extractor 역할)
def load_scenario_data():
    # 파일 경로 설정 (업로드된 폴더 구조 반영)
    csv_path = "data_center_ed_agent/datacenter_load/15_min_data.csv" 
    
    if not os.path.exists(csv_path):
        print(f"경고: {csv_path} 파일이 없습니다. 더미 데이터를 생성합니다.")
        demand_list = [300 + i%50 for i in range(96)] # 15분 단위 24시간 = 96구간
    else:
        # CSV 로드 (컬럼명이 'Load_MW'라고 가정, 실제 파일 확인 필요)
        try:
            df = pd.read_csv(csv_path)
            # 첫 번째 컬럼이나 특정 컬럼을 수요 데이터로 사용
            # 여기서는 편의상 첫번째 숫자 컬럼을 가져옵니다.
            numeric_cols = df.select_dtypes(include=['float', 'int']).columns
            demand_list = df[numeric_cols[0]].tolist()
        except Exception as e:
            print(f"CSV 로드 에러: {e}")
            demand_list = [300] * 96

    # 96개 구간(24시간)으로 맞춤
    T = len(demand_list)
    
    # 2. 파라미터 구성 (Parsing Agent가 만들어서 넘겨줄 데이터 구조를 여기서 직접 정의)
    parsed_data = {
        "time_steps": T,
        "demand": demand_list,
        "components": {
            # [Grid] 전력망 정보
            "grid": {
                # 시간대별 가격 (예: 낮에는 비싸고 밤에는 싸게)
                "price_schedule": [100 if 9 <= (i/4) % 24 <= 18 else 50 for i in range(T)],
                "limit": 1000  # 수전 용량 1000MW
            },
            
            # [MGT] 가스터빈 정보
            "mgt": {
                "min": 10,
                "max": 500,
                "ramp_rate": 50,    # 15분당 50MW 증감 가능
                "cost_coeff": 120   # 운영 비용 (단순화)
            },
            
            # [ESS] 배터리 정보 (이걸 주석 처리하면 모델에서 자동으로 빠짐 -> Adaptive!)
            "ess": {
                "capacity": 800,    # 800MWh
                "efficiency": 0.95,
                "initial_soc": 400  # 시작할 때 50% 충전됨
            }
            
            # # [PV] 태양광 정보 (예시: 낮 12시 근처에만 발전)
            # "pv": {
            #     "forecast": [200 * max(0, -((i/4 - 12)**2)/36 + 1) for i in range(T)]
            # }

        }
    }
    return parsed_data


# ... (load_scenario_data 함수 등 기존 코드) ...

# =========================================================
# [추가] 결과 시각화 함수
# =========================================================
def plot_results(solution_data, parsed_data):
    if not solution_data:
        print("시각화할 데이터가 없습니다.")
        return

    # 1. 데이터 추출
    time_steps = parsed_data['time_steps']
    times = range(time_steps)
    
    # 시간 문자열 (X축 라벨)
    time_labels = [f"{int(t/4):02d}:{int(t%4)*15:02d}" for t in times]

    p_grid = []
    p_mgt = []
    # p_ess_dis = [] # ESS 방전량 (있다면 추가)
    
    # 솔루션에서 값 추출 (없으면 0 처리)
    for t in times:
        val = solution_data.get(t, {})
        p_grid.append(val.get('P_grid', 0))
        p_mgt.append(val.get('P_mgt', 0))
        # p_ess_dis.append(val.get('P_discharge', 0)) 

    # 2. 스택(Stack) 데이터 준비 [수정됨]
    # 순서: 맨 아래 Grid (가장 큰 비중) -> 그 위 MGT
    labels = ["Grid Import", "MGT (Self-Gen)"]
    colors = ["#1f77b4", "#2ca02c"] # 파랑(수전), 초록(자가발전)
    
    # 데이터 배열 (numpy로 변환)
    y_grid = np.array(p_grid)
    y_mgt = np.array(p_mgt)

    # 3. 그래프 그리기
    plt.figure(figsize=(12, 6))
    
    # 스택 면적 차트 (먼저 넣은 게 아래에 깔림)
    plt.stackplot(times, y_grid, y_mgt, labels=labels, colors=colors, alpha=0.8)
    
    # 4. 꾸미기
    plt.title("AI Data Center Energy Mix Optimization", fontsize=15, fontweight='bold')
    plt.ylabel("Power (MW)", fontsize=12)
    plt.xlabel("Time (24h)", fontsize=12)
    
    # X축 눈금 (3시간 간격)
    plt.xticks(ticks=range(0, 96, 12), labels=[time_labels[i] for i in range(0, 96, 12)])
    plt.xlim(0, 95)
    
    # 그리드 및 범례
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(loc='upper left')
    
    # 5. 저장 및 출력
    save_path = "optimization_result.png"
    plt.savefig(save_path)
    print(f"\n[Graph] 결과 그래프가 '{save_path}'로 저장되었습니다.")
    plt.show()
    
    
# =========================================================
# [추가] PDF 보고서 생성 함수
# =========================================================
# main.py 상단 import 추가 (Enums 필요)
from fpdf import FPDF
from fpdf.enums import XPos, YPos 

# ... (기존 load_scenario_data, plot_results 함수들) ...

# =========================================================
# [수정됨] PDF 보고서 생성 함수 (폰트 깨짐 해결 & 최신 문법 적용)
# =========================================================
def create_pdf_report(explanation_text, image_path, filename="Final_Report.pdf"):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. 한글 폰트 등록 (NanumGothic.ttf 추천)
    # 폰트 파일이 프로젝트 폴더(main.py 옆)에 있어야 합니다.
    font_path = 'NanumGothic-Regular.ttf'  # 나눔고딕 파일명 (혹은 malgun.ttf)
    
    if not os.path.exists(font_path):
        # 폰트가 없으면 맑은 고딕(malgun.ttf)으로 시도
        font_path = 'malgun.ttf'
    
    try:
        # 유니코드 지원을 위해 fname 지정
        pdf.add_font('KoreanFont', '', fname=font_path)
        pdf.set_font('KoreanFont', '', 16)
        print(f"[PDF] 폰트 로드 성공: {font_path}")
    except Exception as e:
        print(f"[Warning] 한글 폰트 로드 실패 ({e}). 기본 폰트를 사용합니다(한글 깨짐).")
        pdf.set_font('Arial', '', 12)

    # 2. 제목 작성 (최신 문법: new_x, new_y 사용)
    pdf.set_font_size(20)
    pdf.cell(0, 15, "AI Data Center Energy Optimization Report", 
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(10)

    # 3. 그래프 이미지 삽입
    if os.path.exists(image_path):
        try:
            # 이미지 너비 조정
            pdf.image(image_path, x=15, w=180)
            pdf.ln(5)
        except Exception as e:
            print(f"[PDF] 이미지 삽입 오류: {e}")
    else:
        pdf.cell(0, 10, "[Graph Image Not Found]", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # 4. 본문 (Explanation) 작성
    pdf.set_font_size(11)
    
    text = explanation_text if explanation_text else "No explanation provided."
    
    pdf.ln(5)
    # multi_cell은 줄바꿈을 자동으로 처리함
    pdf.multi_cell(0, 8, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # 5. 저장
    try:
        pdf.output(filename)
        print(f"\n[PDF] 최종 보고서가 '{filename}'로 성공적으로 생성되었습니다!")
    except Exception as e:
        print(f"[Error] PDF 생성 실패: {e}")
        
if __name__ == "__main__":
    # 1. 그래프 빌드
    graph = build_graph()

    # 2. 시나리오 데이터 로드
    scenario_data = load_scenario_data()
    print(f"데이터 로드 완료: 총 {scenario_data['time_steps']} 타임스텝")

    # 3. 초기 상태 설정
    # 주의: 'problem_text'는 이제 참고용이거나 비워둬도 됨
    # 핵심은 'params'에 우리가 만든 데이터를 직접 꽂아넣는 것!
    initial_state = {
        "problem_text": "Time-series optimization for AI Data Center", 
        "params": scenario_data,  # <--- 여기에 데이터를 주입합니다.
        "formulated": None,
        "solution": None,
        "explanation": None,
    }

    # 4. 그래프 실행
    print(">>> 워크플로우 실행 중...")
    try:
        # [중요] 실행 결과를 'result' 변수에 받습니다.
        result = graph.invoke(initial_state)

        # 5. 결과 출력
        print("\n------ PARSED PARAMS (Input) ------")
        if result.get("params") and "demand" in result["params"]:
            print(f"Demand (first 5): {result['params']['demand'][:5]}...")
        
        print("\n------ SOLUTION (Full Schedule) ------")
        sol = result.get("solution_output") 
        
        if sol:
            print(f"💰 Total Daily Cost: {sol.get('Total_Cost', 'N/A'):,.0f} KRW")
            print("-" * 60)
            print(f"{'Time':^10} | {'P_grid (MW)':^15} | {'P_mgt (MW)':^15} | {'Cost':^15}")
            print("-" * 60)
            
            # 0번부터 95번까지 반복하면서 출력
            for t in range(scenario_data['time_steps']):
                if t in sol:
                    # 현재 시간대 비용 계산 (검증용)
                    # 실제로는 Grid 가격이 시간대별로 다르므로 여기선 단순 참고용
                    p_grid = sol[t].get('P_grid', 0)
                    p_mgt = sol[t].get('P_mgt', 0)
                    
                    # 15분 단위를 시간(HH:MM)으로 변환해서 보여줌
                    hour = int(t / 4)
                    minute = (t % 4) * 15
                    time_str = f"{hour:02d}:{minute:02d}"
                    
                    cost_sum=p_grid+p_mgt
                    
                    print(f"{time_str:^10} | {p_grid:^15.2f} | {p_mgt:^15.2f} |{cost_sum:^15.2f}")
            print("-" * 60)
       
        else:
            print("No solution found.")

        print("\n------ EXPLANATION ------")
        # [수정] final_state -> result 로 변경
        print(result.get("explanation"))
        # [추가] 그래프 그리기 함수 호출!
        # 1. 그래프 그리기
        if result.get("solution_output"):
            print("\n>>> 그래프 생성 중...")
            plot_results(result.get("solution_output"), scenario_data)
            
            # 2. [추가] PDF 보고서 생성 호출
            # 그래프 이미지 파일명('optimization_result.png')은 plot_results 함수에서 저장한 이름과 같아야 함
            print("\n>>> PDF 보고서 생성 중...")
            create_pdf_report(
                explanation_text=result.get("explanation"),
                image_path="optimization_result.png",
                filename="AI_DataCenter_Final_Report.pdf"
            )
        
    except Exception as e:
        print(f"\n[Error] 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()