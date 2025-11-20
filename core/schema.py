# core/schema.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any


# ➊ Forecasting Agent 입력/출력 -----------------------------

@dataclass
class ForecastInput:
    """
    데이터센터 수요/재생에너지 예측을 위한 입력 스키마
    """
    cpu_usage: List[float]          # 과거 CPU 사용률 (%)
    gpu_usage: List[float]          # 과거 GPU 사용률 (%)
    history_load: List[float]       # 과거 전력 부하 (kW)
    weather: Dict[str, Any] | None = None  # 온도, 일사량 등 (옵션)


@dataclass
class ForecastOutput:
    """
    향후 일정 구간에 대한 부하/재생에너지 예측 결과
    """
    load_forecast: List[float]      # 예측 부하 (kW)
    pv_forecast: List[float]        # 태양광 발전량 예측 (kW)
    horizon_hours: int              # 예측 시간 길이 (시간)


# ➋ Optimization Agent 입력/출력 -----------------------------

@dataclass
class OptimizationInput:
    """
    ED(경제급전) 최적화에 사용될 입력 정보
    """
    load_forecast: List[float]
    pv_forecast: List[float]
    grid_price: List[float]        # 시간대별 계통 전기요금 (원/kWh)
    ess_capacity: float            # ESS 용량 (kWh)
    ess_soc_init: float            # 초기 SOC (%)
    ess_charge_power_max: float    # 충전 최대 전력 (kW)
    ess_discharge_power_max: float # 방전 최대 전력 (kW)
    mgt_cost: float                # MGT 단위비용 (원/kWh) – 단순 상수 가정
    smr_cost: float                # SMR 단위비용 (원/kWh)
    smr_power_max: float           # SMR 최대출력 (kW)
    horizon_hours: int


@dataclass
class Schedule:
    """
    시간대별 전원별 스케줄
    """
    grid: List[float]
    pv_used: List[float]
    ess_charge: List[float]
    ess_discharge: List[float]
    mgt: List[float]
    smr: List[float]


@dataclass
class OptimizationOutput:
    """
    ED 최적화 결과
    """
    schedule: Schedule
    total_cost: float


# ➌ Planning Agent 입력/출력 -----------------------------

@dataclass
class PlanningInput:
    """
    운영 지시문 생성을 위한 입력
    """
    forecast: ForecastOutput
    optimization_result: OptimizationOutput


@dataclass
class PlanningOutput:
    """
    자연어 보고서 + 핵심 포인트
    """
    natural_language_report: str
    key_points: List[str]
