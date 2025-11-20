# agents/planning_agent.py
from __future__ import annotations
from typing import List
from core.schema import PlanningInput, PlanningOutput


class PlanningAgent:
    """
    최적화 결과를 자연어로 정리해 운영지시문/요약 리포트를 만드는 Agent.
    지금은 LLM 없이 rule-based 텍스트 생성 예시만 넣어두고,
    나중에 OpenAI API 같은 걸 붙일 수 있게 구조만 잡는다.
    """

    def run(self, planning_input: PlanningInput) -> PlanningOutput:
        schedule = planning_input.optimization_result.schedule
        total_cost = planning_input.optimization_result.total_cost
        horizon = planning_input.forecast.horizon_hours

        # 피크 시간대(그리드 사용량 상위 몇 시간) 찾기
        grid = schedule.grid
        peak_hours = sorted(range(horizon), key=lambda t: grid[t], reverse=True)[:3]

        key_points: List[str] = []
        key_points.append(f"총 전력 비용은 약 {total_cost:,.0f} 원으로 추정됩니다.")
        key_points.append(f"그리드 사용량이 가장 높은 시간대는 {peak_hours} 시점입니다.")
        key_points.append("피크 시간대에는 ESS 방전을 통해 비용을 절감하도록 설계했습니다.")

        report_lines: List[str] = []
        report_lines.append("📌 데이터센터 전력 운영 계획 요약")
        report_lines.append("")
        report_lines.append(f"- 전체 계획 기간: {horizon}시간")
        report_lines.append(f"- 추정 총 비용: {total_cost:,.0f} 원")
        report_lines.append("")
        report_lines.append("1️⃣ 그리드(Grid) 사용 전략")
        report_lines.append(f"   - 피크 시간대(상위 3개 시간대): {peak_hours}")
        report_lines.append("   - 피크 시간대에는 ESS 방전량을 최대한 활용하여 Grid 사용량을 줄였습니다.")
        report_lines.append("")
        report_lines.append("2️⃣ ESS 운용 전략")
        report_lines.append("   - 전기요금이 상대적으로 낮은 시간대에 충전하고,")
        report_lines.append("     요금이 높은 피크 시간대에 방전하는 형태로 스케줄링했습니다.")
        report_lines.append("")
        report_lines.append("3️⃣ SMR / MGT 운용")
        report_lines.append("   - SMR은 기본 부하를 담당하는 베이스 전원으로 사용했습니다.")
        report_lines.append("   - MGT는 현재 템플릿에서는 사용하지 않았지만, 비용/제약조건에 따라 추가 가능합니다.")
        report_lines.append("")
        report_lines.append("이 계획은 예측된 부하/태양광 발전량을 기반으로 한 단순 모델이며,")
        report_lines.append("실제 운영 환경에서는 추가적인 안전 제약 및 운영자의 판단이 필요합니다.")

        return PlanningOutput(
            natural_language_report="\n".join(report_lines),
            key_points=key_points,
        )
