# agents/forecasting_agent.py
from __future__ import annotations
from typing import Optional
from core.schema import ForecastInput, ForecastOutput


class ForecastingAgent:
    """
    데이터센터 전력 수요 및 재생에너지(PV) 예측을 담당하는 Agent.
    현재는 아주 단순한 baseline(이동 평균)만 구현해두고,
    이후에 Time Series / ML 모델로 교체할 수 있게 구조만 잡아둔다.
    """

    def __init__(self, horizon_hours: int = 24, window: int = 24):
        self.horizon_hours = horizon_hours
        self.window = window

    def run(self, input_data: ForecastInput) -> ForecastOutput:
        """
        아주 단순하게:
        - 과거 load의 마지막 window 구간 평균을 앞으로 horizon_hours 동안 그대로 사용
        - PV는 일단 0으로 두고, 나중에 태양광 모델 붙이기
        """
        history = input_data.history_load
        if len(history) == 0:
            raise ValueError("history_load is empty")

        window_vals = history[-self.window :] if len(history) >= self.window else history
        avg_load = sum(window_vals) / len(window_vals)

        load_forecast = [avg_load for _ in range(self.horizon_hours)]
        pv_forecast = [0.0 for _ in range(self.horizon_hours)]  # TODO: PV 예측 모델 추가

        return ForecastOutput(
            load_forecast=load_forecast,
            pv_forecast=pv_forecast,
            horizon_hours=self.horizon_hours,
        )
