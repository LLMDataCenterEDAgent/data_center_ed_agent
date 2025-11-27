# core/state.py

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class EDAgentState(BaseModel):

    # ===========================
    # 1) ED Numerical State
    # ===========================
    time: int = 0
    datacenter_load: Optional[float] = None
    grid_price: Optional[float] = None
    solar_gen: Optional[float] = None
    ess_soc: Optional[float] = None
    mgt_output: Optional[float] = None

    # 제약조건(숫자형)
    constraint_values: Dict[str, float] = Field(default_factory=dict)

    # ===========================
    # 2) LLM-Agent 파이프라인
    # ===========================
    scenario: str = ""
    extracted_params: Dict[str, Any] = Field(default_factory=dict)
    constraints: str = ""           # LLM이 만든 제약식(문자열)
    model_code: str = ""            # 생성된 Pyomo/Gurobi 코드
    solution_summary: str = ""      # 솔버 결과 요약
    constraint_violation: bool = False

    # ===========================
    # 3) Agent Logs
    # ===========================
    logs: List[str] = Field(default_factory=list)
