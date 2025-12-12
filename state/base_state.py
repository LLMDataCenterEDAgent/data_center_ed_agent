# state/base_state.py

from typing import TypedDict, Optional, Any

# [중요] 클래스 이름을 'AgentState'로 통일합니다.
class AgentState(TypedDict, total=False):
    # 사용자 입력
    problem_text: str

    # Parsing 결과
    parsed_data: Optional[dict]

    # Formulation 결과 (EDParams 객체)
    params: Optional[Any]

    # Solver 결과 (원본 객체)
    solution: Optional[Any]

    # [핵심] Solver 결과 (Dict 변환본) - ★이 줄이 반드시 있어야 합니다!★
    solution_output: Optional[dict]

    # Explanation Agent 결과
    explanation: Optional[str]