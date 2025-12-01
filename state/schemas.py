# state/schemas.py


from dataclasses import dataclass
from typing import Dict, Optional, Any

@dataclass
class GeneratorSpec:
    name: str
    a: float
    b: float
    c: float
    p_min: float
    p_max: float

@dataclass
class EDParams:
    generators: Dict[str, GeneratorSpec]
    demand: float

@dataclass
class EDSolution:
    Pg: Dict[str, float]                  # 발전기 출력 (예: {"G1": 250, "G2": 250})
    cost: float                           # 총 비용 F1+F2
    note: Optional[str] = None            # 솔버 상태 메모

    # 🔽 새로 추가되는 정보들
    lambda_val: Optional[float] = None    # 시스템 한계비용 λ (가능하면)
    fuel_costs: Optional[Dict[str, float]] = None  # 각 발전기 연료비 { "G1": F1, "G2": F2 }
    balance_violation: Optional[float] = None      # (P1+P2) - D (0이면 제약 정확히 만족)
    slacks: Optional[Dict[str, Dict[str, float]]] = None  
    # 예: { "G1": {"lower": P1-P1_min, "upper": P1_max-P1}, ... }