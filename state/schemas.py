# state/schemas.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class GeneratorSpec:
    name: str
    a: float  # Quadratic term
    b: float  # Linear term
    c: float  # Constant term
    p_min: float
    p_max: float
    ramp_rate: float
    cost_coeff: float = 0.0  # Optional linear cost if a,b,c are 0

@dataclass
class StorageSpec:
    name: str
    capacity_mwh: float
    max_power_mw: float
    efficiency: float
    initial_soc: float
    min_soc: float
    max_soc: float
    aging_cost: float

@dataclass
class RenewableSpec:
    name: str
    profile: List[float]

@dataclass
class EDParams:
    is_time_series: bool
    time_steps: int
    demand_profile: List[float]
    generators: Dict[str, GeneratorSpec]
    
    # Optional fields
    pv_profile: Optional[List[float]] = None
    ess: Optional[Dict[str, StorageSpec]] = None
    grid_price_profile: Optional[List[float]] = None
    timestamps: Optional[List[str]] = None
    
    # [핵심 수정] 여기에 base_rate를 추가해야 에러가 안 납니다!
    base_rate: float = 0.0 

@dataclass
class EDSolution:
    cost: float = 0.0
    schedule: Dict[str, List[float]] = field(default_factory=dict)
    ess_schedule: Dict[str, Dict[str, List[float]]] = field(default_factory=dict)