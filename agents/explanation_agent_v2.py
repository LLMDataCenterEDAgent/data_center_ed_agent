from openai import OpenAI

from state.base_state import AgentState
from utils.runtime_secrets import load_streamlit_secrets_into_env


client = None


SYSTEM_PROMPT = """
You are a professional energy systems analyst.
Write a comprehensive technical report in English using only the provided input data.

Requirements:
- Use a professional technical report style in the third person and remain objective.
- Do not invent or estimate missing data.
- Interpret the provided numerical values with ratios, comparisons, and contextual meaning.
- Keep the output as plain text only.
- Use exactly these section headings:
1. Executive Summary
2. System Configuration Analysis
3. Cost Structure Analysis
4. Dispatch Strategy Analysis by Generation Source
5. TOU-Based Operation Strategy Analysis
6. Overall Assessment and Recommendations
7. Data Limitations and Assumptions
- In Section 6, include at least 3 specific recommendations.
- In Section 7, explicitly state assumptions and data limitations rather than inventing extra operating conditions.
"""


def calc_generation_cost(spec, power):
    if spec.a != 0 or spec.b != 0 or spec.c != 0:
        return spec.a * power ** 2 + spec.b * power + spec.c
    if getattr(spec, "cost_coeff", 0):
        return power * spec.cost_coeff
    return 0.0


class ExplanationAgent:
    def run(self, state: AgentState) -> AgentState:
        global client
        print("\n--- Explanation Agent Started (LLM Technical Report Mode) ---")

        sol = state.get("solution_output")
        params = state.get("params")

        if not sol or not params:
            state["explanation"] = "Error generating explanation."
            return state

        try:
            if client is None:
                load_streamlit_secrets_into_env()
                client = OpenAI()

            total_cost = float(sol.get("Total_Cost", 0.0))
            fixed_base_cost = float(getattr(params, "base_rate", 0.0) or 0.0)
            variable_cost = total_cost - fixed_base_cost

            gen_names = list(params.generators.keys())
            ess_names = list(params.ess.keys()) if params.ess else []
            time_steps = params.time_steps
            interval_hours = float(getattr(params, "interval_hours", 0.25) or 0.25)
            interval_minutes = int(getattr(params, "interval_minutes", 15) or 15)
            horizon_hours = time_steps * interval_hours

            gt_names = [g for g in gen_names if "GT" in g.upper() or "GAS" in g.upper()]
            smr_names = [g for g in gen_names if "SMR" in g.upper() or "NUC" in g.upper()]

            gt_capacity = sum(params.generators[g].p_max for g in gt_names)
            smr_capacity = sum(params.generators[g].p_max for g in smr_names)
            pv_capacity = max(params.pv_profile) if params.pv_profile else 0.0
            ess_power = sum(params.ess[e].max_power_mw for e in ess_names) if ess_names else 0.0
            ess_capacity = sum(params.ess[e].capacity_mwh for e in ess_names) if ess_names else 0.0

            prices = params.grid_price_profile if params.grid_price_profile else [0.0] * time_steps
            unique_prices = sorted(set(prices))
            tou_map = {}
            if len(unique_prices) >= 3:
                tou_map[unique_prices[0]] = "Off-Peak"
                tou_map[unique_prices[-1]] = "On-Peak"
                for price in unique_prices[1:-1]:
                    tou_map[price] = "Mid-Peak"
            elif len(unique_prices) == 2:
                tou_map[unique_prices[0]] = "Off-Peak"
                tou_map[unique_prices[-1]] = "On-Peak"
            elif len(unique_prices) == 1:
                tou_map[unique_prices[0]] = "Flat"

            gt_total = 0.0
            smr_total = 0.0
            pv_total = 0.0
            ess_total = 0.0
            smr_cost = 0.0
            tou_stats = {}

            for t in range(time_steps):
                row = sol.get(t, {})
                if not row:
                    continue

                gt_output = sum(row.get(f"P_{g}", 0.0) for g in gt_names)
                smr_output = sum(row.get(f"P_{g}", 0.0) for g in smr_names)
                pv_output = row.get("P_PV", 0.0)
                ess_output = sum(row.get(f"P_dis_{e}", 0.0) for e in ess_names)
                ess_soc = sum(row.get(f"SOC_{e}", 0.0) for e in ess_names)

                gt_total += gt_output
                smr_total += smr_output
                pv_total += pv_output
                ess_total += ess_output

                for g in smr_names:
                    smr_cost += calc_generation_cost(params.generators[g], row.get(f"P_{g}", 0.0))

                label = tou_map.get(prices[t], "Flat")
                if label not in tou_stats:
                    tou_stats[label] = {"count": 0, "smr": 0.0, "gt": 0.0, "pv": 0.0, "ess": 0.0, "soc": 0.0}
                tou_stats[label]["count"] += 1
                tou_stats[label]["smr"] += smr_output
                tou_stats[label]["gt"] += gt_output
                tou_stats[label]["pv"] += pv_output
                tou_stats[label]["ess"] += ess_output
                tou_stats[label]["soc"] += ess_soc

            gt_avg = gt_total / time_steps if time_steps else 0.0
            smr_avg = smr_total / time_steps if time_steps else 0.0
            pv_avg = pv_total / time_steps if time_steps else 0.0
            ess_avg = ess_total / time_steps if time_steps else 0.0

            pv_energy = pv_total * interval_hours
            ess_energy = ess_total * interval_hours

            baseload_ratio = (smr_cost / total_cost * 100.0) if total_cost else 0.0
            variable_ratio = (variable_cost / total_cost * 100.0) if total_cost else 0.0
            gt_cf = (gt_avg / gt_capacity * 100.0) if gt_capacity else 0.0
            smr_cf = (smr_avg / smr_capacity * 100.0) if smr_capacity else 0.0
            pv_cf = (pv_energy / (pv_capacity * horizon_hours) * 100.0) if pv_capacity and horizon_hours else 0.0
            ess_cf = (ess_energy / (ess_power * horizon_hours) * 100.0) if ess_power and horizon_hours else 0.0

            tou_lines = []
            for label in ["Off-Peak", "Mid-Peak", "On-Peak", "Flat"]:
                stat = tou_stats.get(label)
                if not stat or stat["count"] == 0:
                    continue
                tou_lines.append(
                    f"- {label}: SMR {stat['smr'] / stat['count']:.1f} MW | "
                    f"GT {stat['gt'] / stat['count']:.1f} MW | "
                    f"PV {stat['pv'] / stat['count']:.1f} MW | "
                    f"ESS {stat['ess'] / stat['count']:.1f} MW / {stat['soc'] / stat['count']:.1f} MWh"
                )

            report_input = f"""
## [INPUT DATA]

### 1. Microgrid Component Configuration
- PV (Photovoltaic): {pv_capacity:.1f} MW
- GT (Gas Turbine): {gt_capacity:.1f} MW
- SMR (Small Modular Reactor): {smr_capacity:.1f} MW
- ESS (Energy Storage System): {ess_power:.1f} MW / {ess_capacity:.1f} MWh

### 2. Cost Optimization Results
- Baseload Generation Cost: {smr_cost:,.0f} KRW
- Variable Cost: {variable_cost:,.0f} KRW
- Total Cost: {total_cost:,.0f} KRW

### 3. Dispatch Optimization Analysis
- SMR: Baseload operation (constant dispatch at {smr_avg:.1f} MW average, capacity factor {smr_cf:.1f}%)
- GT: Flexible generation source (average {gt_avg:.1f} MW, capacity factor {gt_cf:.1f}%)
- PV: Peak renewable support (average {pv_avg:.1f} MW, total {pv_energy:.1f} MWh, capacity factor {pv_cf:.1f}%)
- ESS: Peak shaving and arbitrage (average discharge {ess_avg:.1f} MW, total discharge {ess_energy:.1f} MWh, discharge-based capacity factor {ess_cf:.1f}%)

### 4. TOU (Time-of-Use) Operation Strategy
{chr(10).join(tou_lines)}

### 5. Cost Ratios and Additional Context
- Baseload cost ratio: {baseload_ratio:.1f}%
- Variable cost ratio: {variable_ratio:.1f}%
- Fixed base cost included in total cost: {fixed_base_cost:,.0f} KRW
- Dispatch interval: {interval_minutes} minutes
- Analysis horizon: {horizon_hours:.1f} hours
- Use only the values above. If a value is missing, state it as a limitation.
"""

            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": report_input},
                ],
                temperature=0.2,
            )

            state["explanation"] = resp.choices[0].message.content
            print(">> Explanation Generated by LLM Technical Report Prompt.")

        except Exception as e:
            print(f"Explanation Error: {e}")
            import traceback
            traceback.print_exc()
            state["explanation"] = "Error generating explanation."

        return state
