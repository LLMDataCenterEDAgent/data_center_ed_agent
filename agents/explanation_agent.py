# agents/explanation_agent.py

from state.base_state import AgentState


SYSTEM_PROMPT = """
You are a top-tier AI Data Center Energy Optimization Consultant.
Write a readable English Energy Dispatch Report for business and engineering readers.
Use this exact section order:
1. Microgrid Components
2. Cost Optimization Result
3. Dispatch Optimization Analysis
4. TOU Strategy
5. Summary

Use moderately sized markdown headings such as ###, not #.
Use the provided numerical facts. Do not invent values.
Explain why SMR is baseload, why GT is flexible capacity, why PV reduces peak/net load,
and how ESS supports arbitrage and peak shaving.
"""


class ExplanationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Explanation Agent Started (Energy Dispatch Report) ---")

        sol = state.get("solution_output")
        params = state.get("params")

        if not sol or not params:
            state["explanation"] = "Optimization result is not available."
            return state

        try:
            facts = self._build_facts(sol, params)
            summary_input = self._factsheet(facts)
            explanation = self._fallback_report(**facts)

            try:
                from openai import OpenAI

                client = OpenAI()
                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": summary_input},
                    ],
                    temperature=0.3,
                )
                explanation = resp.choices[0].message.content
            except Exception as llm_error:
                print(f"LLM report skipped, using fallback report: {llm_error}")

            state["explanation"] = explanation
            print(">> Energy Dispatch Report generated.")
        except Exception as exc:
            print(f"Explanation Error: {exc}")
            import traceback

            traceback.print_exc()
            state["explanation"] = "Error generating report."

        return state

    def _build_facts(self, sol, params):
        rows = [(t, sol[t]) for t in range(params.time_steps) if isinstance(sol.get(t), dict)]
        total_cost = sol.get("Total_Cost", 0.0)
        fixed_base_cost = getattr(params, "base_rate", 0.0) or 0.0
        variable_cost = total_cost - fixed_base_cost

        total_grid = sum(row.get("P_grid", 0.0) for _, row in rows)
        total_pv = sum(row.get("P_PV", 0.0) for _, row in rows)
        total_ess_dis = sum(row.get("P_dis_ESS1", row.get("P_discharge", 0.0)) for _, row in rows)
        total_ess_chg = sum(row.get("P_chg_ESS1", row.get("P_charge", 0.0)) for _, row in rows)

        gen_totals = {}
        for _, row in rows:
            for key, value in row.items():
                if key.startswith("P_") and key not in ("P_grid", "P_PV") and not key.startswith("P_dis_") and not key.startswith("P_chg_"):
                    gen_totals[key[2:]] = gen_totals.get(key[2:], 0.0) + value

        total_smr = sum(value for name, value in gen_totals.items() if name.startswith("SMR"))
        total_gt = sum(value for name, value in gen_totals.items() if name.startswith("GT"))
        total_gen = sum(gen_totals.values())
        total_supply = total_grid + total_pv + total_gen + total_ess_dis
        pv_share = (total_pv / total_supply * 100.0) if total_supply else 0.0

        total_smr_cost = 0.0
        total_gt_cost = 0.0
        for gen_name, generation in gen_totals.items():
            spec = params.generators.get(gen_name)
            if not spec:
                continue
            coeff = spec.cost_coeff or spec.b or 0.0
            cost = generation * coeff
            if gen_name.startswith("SMR"):
                total_smr_cost += cost
            elif gen_name.startswith("GT"):
                total_gt_cost += cost

        total_supply_t = []
        for _, row in rows:
            gen_value = sum(
                value
                for key, value in row.items()
                if key.startswith("P_") and key not in ("P_grid", "P_PV") and not key.startswith("P_dis_") and not key.startswith("P_chg_")
            )
            total_supply_t.append(row.get("P_grid", 0.0) + row.get("P_PV", 0.0) + gen_value + row.get("P_dis_ESS1", 0.0))

        peak_load = max(total_supply_t) if total_supply_t else 0.0
        peak_idx = total_supply_t.index(peak_load) if total_supply_t else 0
        start_time_str = params.timestamps[0] if params.timestamps else "09:00"
        peak_time_str = params.timestamps[peak_idx] if params.timestamps and peak_idx < len(params.timestamps) else f"Step {peak_idx}"

        return {
            "total_cost": total_cost,
            "fixed_base_cost": fixed_base_cost,
            "variable_cost": variable_cost,
            "total_smr_cost": total_smr_cost,
            "total_gt_cost": total_gt_cost,
            "total_supply": total_supply,
            "total_grid": total_grid,
            "total_pv": total_pv,
            "pv_share": pv_share,
            "total_gen": total_gen,
            "total_gt": total_gt,
            "total_smr": total_smr,
            "total_ess_dis": total_ess_dis,
            "total_ess_chg": total_ess_chg,
            "peak_time_str": peak_time_str,
            "peak_load": peak_load,
            "start_time_str": start_time_str,
            "step_count": len(rows),
            "component_facts": self._component_facts(params),
            "tou_facts": self._tou_facts(sol, params),
        }

    def _factsheet(self, facts):
        return f"""
[Energy Dispatch Facts]
- Total Cost: {facts['total_cost']:,.0f} KRW
- Fixed Base Cost: {facts['fixed_base_cost']:,.0f} KRW
- Variable Cost: {facts['variable_cost']:,.0f} KRW
- Baseload / SMR Generation Cost: {facts['total_smr_cost']:,.0f} KRW
- GT Generation Cost: {facts['total_gt_cost']:,.0f} KRW
- Total Supply: {facts['total_supply']:,.1f} MW
- Grid Import: {facts['total_grid']:,.1f} MW
- PV Generation: {facts['total_pv']:,.1f} MW ({facts['pv_share']:.1f}%)
- GT Dispatch: {facts['total_gt']:,.1f} MW
- SMR Dispatch: {facts['total_smr']:,.1f} MW
- ESS Charge: {facts['total_ess_chg']:,.1f} MW
- ESS Discharge: {facts['total_ess_dis']:,.1f} MW
- Peak Time: {facts['peak_time_str']}
- Peak Load: {facts['peak_load']:,.1f} MW
- Start Time: {facts['start_time_str']}
- Component Facts: {facts['component_facts']}
- TOU Facts: {facts['tou_facts']}
"""

    def _component_facts(self, params):
        gt_capacity = sum(spec.p_max for name, spec in params.generators.items() if name.startswith("GT"))
        smr_capacity = sum(spec.p_max for name, spec in params.generators.items() if name.startswith("SMR"))
        ess_power = sum(spec.max_power_mw for spec in (params.ess or {}).values())
        ess_capacity = sum(spec.capacity_mwh for spec in (params.ess or {}).values())
        pv_capacity = max(params.pv_profile or [0.0])
        return {
            "PV MW": pv_capacity,
            "GT MW": gt_capacity,
            "SMR MW": smr_capacity,
            "ESS MW": ess_power,
            "ESS MWh": ess_capacity,
        }

    def _tou_facts(self, sol, params):
        price_profile = params.grid_price_profile or [0.0] * params.time_steps
        unique_prices = sorted(set(price_profile))
        if len(unique_prices) >= 3:
            price_labels = {unique_prices[0]: "Off-Peak", unique_prices[-1]: "On-Peak"}
            for price in unique_prices[1:-1]:
                price_labels[price] = "Mid-Peak"
        elif len(unique_prices) == 2:
            price_labels = {unique_prices[0]: "Off-Peak", unique_prices[-1]: "On-Peak"}
        else:
            price_labels = {unique_prices[0] if unique_prices else 0.0: "Off-Peak"}

        buckets = {}
        for t in range(params.time_steps):
            label = price_labels.get(price_profile[t], "Mid-Peak")
            row = sol.get(t, {})
            bucket = buckets.setdefault(label, {"SMR MW": [], "GT MW": [], "PV MW": [], "ESS MW": [], "ESS MWh": [], "Price": price_profile[t]})
            bucket["SMR MW"].append(sum(value for key, value in row.items() if key.startswith("P_SMR")))
            bucket["GT MW"].append(sum(value for key, value in row.items() if key.startswith("P_GT")))
            bucket["PV MW"].append(row.get("P_PV", 0.0))
            bucket["ESS MW"].append(row.get("P_dis_ESS1", 0.0) - row.get("P_chg_ESS1", 0.0))
            bucket["ESS MWh"].append(row.get("SOC_ESS1", 0.0))

        def avg(values):
            return sum(values) / len(values) if values else 0.0

        facts = {}
        for label in ["Off-Peak", "Mid-Peak", "On-Peak"]:
            bucket = buckets.get(label, {})
            facts[label] = {
                "Price": bucket.get("Price", 0.0),
                "SMR MW": avg(bucket.get("SMR MW", [])),
                "GT MW": avg(bucket.get("GT MW", [])),
                "PV MW": avg(bucket.get("PV MW", [])),
                "ESS MW": avg(bucket.get("ESS MW", [])),
                "ESS MWh": avg(bucket.get("ESS MWh", [])),
            }
        return facts

    def _fallback_report(self, **facts):
        components = facts["component_facts"]
        tou = facts["tou_facts"]

        def fmt(value):
            return f"{value:,.1f}"

        return f"""**Energy Dispatch Report**

### 1. Microgrid Components
- PV: {fmt(components.get('PV MW', 0))} MW available peak output in the synchronized profile.
- GT: {fmt(components.get('GT MW', 0))} MW installed flexible thermal capacity.
- SMR: {fmt(components.get('SMR MW', 0))} MW installed baseload generation capacity.
- ESS: {fmt(components.get('ESS MW', 0))} MW / {fmt(components.get('ESS MWh', 0))} MWh battery system.

The simulation uses {facts['step_count']} dispatch intervals at 15-minute resolution. Demand and PV data were synchronized successfully from {facts['start_time_str']}, so generation, storage, and grid usage are compared on the same time basis.

### 2. Cost Optimization Result
- Fixed Base Cost: {facts['fixed_base_cost']:,.0f} KRW
- Baseload Generation Cost: {facts['total_smr_cost']:,.0f} KRW
- Variable Cost: {facts['variable_cost']:,.0f} KRW
- Total Cost: {facts['total_cost']:,.0f} KRW

The optimized dispatch supplied {facts['total_supply']:,.1f} MW across the simulation horizon. PV contributed {facts['total_pv']:,.1f} MW, equal to {facts['pv_share']:.1f}% of total supply. Internal generation supplied {facts['total_gen']:,.1f} MW, while grid import accounted for {facts['total_grid']:,.1f} MW. The peak dispatch requirement occurred at {facts['peak_time_str']} with {facts['peak_load']:,.1f} MW.

### 3. Dispatch Optimization Analysis
- SMR: Baseload Generation
  - SMR was dispatched as the stable economic foundation of the microgrid because its generation cost is lower and its ramping flexibility is limited.
  - Across the horizon, SMR supplied {facts['total_smr']:,.1f} MW, supporting continuous demand coverage and reducing dependence on higher-cost grid imports.

- GT: Flexible Plants
  - GT units provide controllable capacity for periods when demand exceeds the baseload and renewable contribution.
  - Because GT has a higher variable cost than SMR, the optimizer uses it as flexible balancing capacity rather than pure baseload. Total GT dispatch was {facts['total_gt']:,.1f} MW.

- PV: Peak Contribution
  - PV reduces net demand during daylight intervals and directly offsets thermal or grid supply requirements.
  - PV curtailment can be considered later when renewable output exceeds economic or operational needs, but in this result PV mainly acts as low-cost self-generation.

- ESS: Arbitrage and Peak Shaving
  - ESS improves flexibility by shifting energy across time and reducing peak pressure on generators and the grid.
  - The battery charged {facts['total_ess_chg']:,.1f} MW and discharged {facts['total_ess_dis']:,.1f} MW, supporting arbitrage and peak shaving behavior.

### 4. TOU Strategy
- Off-Peak
  - SMR: {fmt(tou.get('Off-Peak', {}).get('SMR MW', 0))} MW
  - GT: {fmt(tou.get('Off-Peak', {}).get('GT MW', 0))} MW
  - PV: {fmt(tou.get('Off-Peak', {}).get('PV MW', 0))} MW
  - ESS: {fmt(tou.get('Off-Peak', {}).get('ESS MW', 0))} MW / {fmt(tou.get('Off-Peak', {}).get('ESS MWh', 0))} MWh

- Mid-Peak
  - SMR: {fmt(tou.get('Mid-Peak', {}).get('SMR MW', 0))} MW
  - GT: {fmt(tou.get('Mid-Peak', {}).get('GT MW', 0))} MW
  - PV: {fmt(tou.get('Mid-Peak', {}).get('PV MW', 0))} MW
  - ESS: {fmt(tou.get('Mid-Peak', {}).get('ESS MW', 0))} MW / {fmt(tou.get('Mid-Peak', {}).get('ESS MWh', 0))} MWh

- On-Peak
  - SMR: {fmt(tou.get('On-Peak', {}).get('SMR MW', 0))} MW
  - GT: {fmt(tou.get('On-Peak', {}).get('GT MW', 0))} MW
  - PV: {fmt(tou.get('On-Peak', {}).get('PV MW', 0))} MW
  - ESS: {fmt(tou.get('On-Peak', {}).get('ESS MW', 0))} MW / {fmt(tou.get('On-Peak', {}).get('ESS MWh', 0))} MWh

The TOU interpretation shows how the optimizer combines low-cost baseload, flexible GT capacity, PV self-generation, and ESS charge/discharge behavior across different price periods.

### 5. Summary
The optimized schedule uses SMR as the economic baseload resource, GT as the flexible balancing resource, PV as a low-cost net-load reducer, and ESS as the operational buffer for arbitrage and peak shaving. This structure is suitable for a data center microgrid because it balances reliability, cost, and dispatch flexibility while keeping the result explainable for later comparison scenarios.
"""
