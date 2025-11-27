# core/state.py
from typing import TypedDict, Dict, Any, Optional

class EDState(TypedDict, total=False):
    scenario: Dict[str, Any]
    data_dict: Dict[str, Any]
    constraint_config: Dict[str, Any]
    model: Any
    solution: Dict[str, Any]
    analysis: str
    next_action: Optional[str]