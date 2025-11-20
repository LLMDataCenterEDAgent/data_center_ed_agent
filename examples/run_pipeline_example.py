# examples/run_pipeline_example.py
from core.schema import (
    ForecastInput,
    OptimizationInput,
    PlanningInput,
)
from agents.forecasting_agent import ForecastingAgent
from agents.optimization_agent import OptimizationAgent
from agents.rule_agent import RuleAgent
from agents.planning_agent import PlanningAgent


def main():
    # 1) 예측 단계 ----------------------------------------
    history_load = [500 + i * 2 for i in range(48)]  # 아주 단순한 예제 데이터
    forecast_input = ForecastInput(
        cpu_usage=[],
        gpu_usage=[],
        history_load=history_load,
        weather=None,
    )

    forecasting_agent = ForecastingAgent(horizon_hours=24)
    forecast_output = forecasting_agent.run(forecast_input)

    # 2) 최적화 단계 --------------------------------------
    H = forecast_output.horizon_hours
    opt_input = OptimizationInput(
        load_forecast=forecast_output.load_forecast,
        pv_forecast=forecast_output.pv_forecast,
        grid_price=[150 + (i % 6) * 20 for i in range(H)],  # 시간대별 요금 예시
        ess_capacity=500.0,
        ess_soc_init=0.5,  # 50%
        ess_charge_power_max=50.0,
        ess_discharge_power_max=50.0,
        mgt_cost=220.0,
        smr_cost=80.0,
        smr_power_max=200.0,
        horizon_hours=H,
    )

    optimization_agent = OptimizationAgent(peak_price_threshold=220.0)
    opt_output = optimization_agent.run(opt_input)

    # 3) 규칙 검증 단계 -----------------------------------
    rule_agent = RuleAgent(ess_soc_min=0.1, ess_soc_max=0.9)
    rule_result = rule_agent.validate(
        result=opt_output,
        ess_capacity=opt_input.ess_capacity,
        ess_soc_init=opt_input.ess_soc_init,
    )

    if not rule_result.valid:
        print("⚠️ 규칙 위반 발생:")
        for v in rule_result.violations:
            print(" -", v)
    else:
        print("✅ 모든 규칙을 만족합니다.")

    # 4) 플래닝/보고서 단계 ------------------------------
    planning_input = PlanningInput(
        forecast=forecast_output,
        optimization_result=opt_output,
    )

    planning_agent = PlanningAgent()
    planning_output = planning_agent.run(planning_input)

    print("\n====== 자연어 보고서 ======\n")
    print(planning_output.natural_language_report)
    print("\n====== Key Points ======\n")
    for p in planning_output.key_points:
        print("-", p)


if __name__ == "__main__":
    main()
