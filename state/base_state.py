# state/base_state.py

from typing import TypedDict, Optional, Any

# 클래스 이름을 'AgentState'로 통일
class AgentState(TypedDict, total=False):
    # 사용자 입력 텍스트
    problem_text: str

    # Parsing 결과 (Dict 구조의 시계열 데이터)
    params: Optional[dict]

    # Formulation 결과 (Pyomo ConcreteModel 객체)
    pyomo_model: Optional[Any]

    # Solver 결과 (시계열 수치 데이터 Dict) - 핵심 키 이름 통일
    solution_output: Optional[dict]

    # 기존 호환성을 위해 solution 키도 남김
    solution: Optional[Any]

    # 최종 설명 (문자열)
    explanation: Optional[str]