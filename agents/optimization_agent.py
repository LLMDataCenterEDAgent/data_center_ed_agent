# agents/optimization_agent.py
from __future__ import annotations
from typing import List
from core.schema import (
    OptimizationInput,
    OptimizationOutput,
    Schedule,
)


class OptimizationAgent:
    """
    ED(경제급전) 문제를 풀어서 시간대별 전원 스케줄을 결정하는 Agent.

    현재 구현:
    - PV를 우선적으로 사용
    - 그 다음 SMR (고정비용이 낮다는 가정)
    - ESS는 피크 시간대에서만 방전 (간단 버전)
    - 나머지는 Grid에서 조달
    """

    def __init__(self, peak_price_threshold: float = 200.0):
        self.peak_price_threshold = peak_price_threshold

    def run(self, opt_input: OptimizationInput) -> OptimizationOutput:
        H = opt_input.horizon_hours

        grid: List[float] = [0.0] * H
        pv_used: List[float] = [0.0] * H
        ess_charge: List[float] = [0.0] * H
        ess_discharge: List[float] = [0.0] * H
        mgt: List[float] = [0.0] * H
        smr: List[float] = [0.0] * H

        soc = opt_input.ess_soc_init * opt_input.ess_capacity / 100.0  # kWh

        total_cost = 0.0

        for t in range(H):
            load = opt_input.load_forecast[t]
            pv = opt_input.pv_forecast[t]
            price = opt_input.grid_price[t]

            remaining = load

            # 1) PV 최대 사용
            use_pv = min(remaining, pv)
            pv_used[t] = use_pv
            remaining -= use_pv

            # 2) SMR 사용 (최대 smr_power_max까지)
            use_smr = min(remaining, opt_input.smr_power_max)
            smr[t] = use_smr
            remaining -= use_smr
            total_cost += use_smr * opt_input.smr_cost

            # 3) 피크 시간대라면 ESS 방전 우선
            if price >= self.peak_price_threshold and remaining > 0:
                possible_discharge = min(
                    opt_input.ess_discharge_power_max,
                    soc,  # 1시간 단위 가정
                    remaining,
                )
                ess_discharge[t] = possible_discharge
                soc -= possible_discharge
                remaining -= possible_discharge
                # ESS 방전은 비용 0으로 가정 (실제로는 round-trip 효율 등 반영 가능)

            # 4) 남은 부하는 Grid + MGT로 충당 (여기선 Grid 우선)
            if remaining > 0:
                # Grid 먼저
                grid[t] = remaining
                total_cost += remaining * price
                remaining = 0.0

            # 5) ESS 충전 (비피크 시간대에 surplus PV 없다고 가정하니 단순히 Grid로 충전해도 됨)
            if price < self.peak_price_threshold * 0.7:
                # 여유있을 때 충전 (간단한 룰)
                charge_power = min(
                    opt_input.ess_charge_power_max,
                    opt_input.ess_capacity - soc,
                )
                if charge_power > 0:
                    ess_charge[t] = charge_power
                    soc += charge_power
                    total_cost += charge_power * price  # 충전도 Grid 전력 구매

        schedule = Schedule(
            grid=grid,
            pv_used=pv_used,
            ess_charge=ess_charge,
            ess_discharge=ess_discharge,
            mgt=mgt,
            smr=smr,
        )

        return OptimizationOutput(schedule=schedule, total_cost=total_cost)
