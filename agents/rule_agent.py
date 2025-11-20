# agents/rule_agent.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List
from core.schema import OptimizationOutput


@dataclass
class RuleCheckResult:
    valid: bool
    violations: List[str]


class RuleAgent:
    """
    운영 규칙(제약조건) 위반 여부를 체크하는 Agent.
    """

    def __init__(self, ess_soc_min: float = 0.1, ess_soc_max: float = 0.9):
        self.ess_soc_min = ess_soc_min
        self.ess_soc_max = ess_soc_max

    def validate(self, result: OptimizationOutput, ess_capacity: float, ess_soc_init: float) -> RuleCheckResult:
        violations: List[str] = []

        soc = ess_soc_init * ess_capacity / 100.0

        for t in range(len(result.schedule.grid)):
            charge = result.schedule.ess_charge[t]
            discharge = result.schedule.ess_discharge[t]
            soc += charge - discharge

            soc_ratio = soc / ess_capacity if ess_capacity > 0 else 0.0
            if soc_ratio < self.ess_soc_min:
                violations.append(f"시간 {t}: ESS SOC가 최소 한도 아래 ({soc_ratio:.2f})")
            if soc_ratio > self.ess_soc_max:
                violations.append(f"시간 {t}: ESS SOC가 최대 한도 초과 ({soc_ratio:.2f})")

        return RuleCheckResult(valid=len(violations) == 0, violations=violations)
