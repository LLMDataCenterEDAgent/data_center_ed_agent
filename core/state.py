# core/state.py

from typing import Dict, Any, List
from pydantic import BaseModel, Field


class EDAgentState(BaseModel):
    scenario: str
    extracted_params: Dict[str, Any] = Field(default_factory=dict)
    constraints: str = ""
    model_code: str = ""
    solution_summary: str = ""
    constraint_violation: bool = False
    logs: List[str] = Field(default_factory=list)
