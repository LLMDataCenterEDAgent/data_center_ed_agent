# state/base_state.py

from typing import TypedDict, Optional, Any


class EDState(TypedDict, total=False):
    # 사용자 입력 문제 텍스트
    problem_text: str

    # Parsing Agent 결과
    params: Optional[Any]

    # Formulation Agent 결과
    formulated: Optional[Any]

    # Solver Agent 결과
    solution: Optional[Any]

    # Explanation Agent 결과 (문장)
    explanation: Optional[str]
