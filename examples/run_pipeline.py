# examples/run_pipeline.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import EDAgentState
from core.graph import build_graph


if __name__ == "__main__":
    scenario = """
    내일 24시간 동안 피크 부하는 10MW이고,
    20~22시에 GPU 작업 증가로 부하가 30% 상승한다.
    ESS는 20MWh, 최대 충/방전 5MW, SOC 20~90%.
    SMR 정격 5MW, 최소 3MW, ramp 1MW/h.
    PV 최대 4MW, 시간대별 발전 예측 사용.
    Grid 가격은 피크에 더 비싸다.
    """

    init = EDAgentState(scenario=scenario)
    graph = build_graph()
    app = graph.compile()
    final = app.invoke(init)

    print("\n===== RESULT =====")
    print(final.solution_summary)

    print("\n===== LOGS =====")
    for log in final.logs:
        print("-", log)
