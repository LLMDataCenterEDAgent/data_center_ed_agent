# state/schemas.py

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

# 1. 발전기 스펙
class GeneratorSpec(BaseModel):
    name: str
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    p_min: float = 0.0
    p_max: float = 0.0
    ramp_rate: Optional[float] = None
    cost_coeff: Optional[float] = None

# 2. ESS 스펙
class StorageSpec(BaseModel):
    name: str
    capacity_mwh: float
    max_power_mw: float
    efficiency: float = 0.95
    initial_soc: float = 0.5
    min_soc: float = 0.1
    max_soc: float = 0.9
    aging_cost: float = 0.0

# 3. 재생에너지(PV) 스펙
class RenewableSpec(BaseModel):
    name: str
    peak_mw: float
    curtailment_cost: float = 0.0

# 4. 전체 파라미터 구조 (EDParams)
class EDParams(BaseModel):
    generators: Dict[str, GeneratorSpec] = Field(default_factory=dict)
    ess: Optional[Dict[str, StorageSpec]] = None
    pv: Optional[Dict[str, RenewableSpec]] = None
    
    # 시계열 관련 설정
    is_time_series: bool = False
    time_steps: int = 1
    demand_profile: Optional[List[float]] = None
    pv_profile: Optional[List[float]] = None
    grid_price_profile: Optional[List[float]] = None
    
    # [핵심 수정] 이 줄이 없어서 에러가 난 것입니다! 꼭 추가해주세요.
    timestamps: Optional[List[str]] = None
    
    pv_reserve_ratio: float = 0.0
    demand: float = 0.0

# 5. 최적화 결과 구조 (EDSolution)
class EDSolution(BaseModel):
    cost: float = 0.0
    note: str = ""
    schedule: Optional[Dict[str, Any]] = None 
    ess_schedule: Optional[Dict[str, Any]] = None