# agents/formulation_agent.py

import os

import numpy as np
import pandas as pd

from state.base_state import AgentState
from state.schemas import EDParams, GeneratorSpec, StorageSpec


class FormulationAgent:
    def run(self, state: AgentState) -> AgentState:
        print("\n--- Formulation Agent Started (Streamlit Scenario + TOU Cost) ---")

        scenario_config = state.get("scenario_config") or {}
        data = state.get("parsed_data")

        if not data:
            net_demand = [300.0] * 96
            pv_profile = [0.0] * 96
            timestamps = None
        else:
            net_demand = data["net_demand_profile"]
            pv_profile = data["pv_profile"]
            timestamps = data.get("timestamps")

        T = len(net_demand)

        gt_count = int(scenario_config.get("gt_count", 2) or 2)
        gt_min = float(scenario_config.get("gt_min", 85) or 85)
        gt_max = float(scenario_config.get("gt_max", 170) or 170)
        gt_cost = float(scenario_config.get("gt_cost", 0.03) or 0.03)
        smr_min = float(scenario_config.get("smr_min", 91) or 91)
        smr_max = float(scenario_config.get("smr_max", 121) or 121)
        smr_cost = float(scenario_config.get("smr_cost", 2500) or 2500)
        ess_capacity = float(scenario_config.get("ess_capacity_mwh", 160) or 160)
        ess_power = float(scenario_config.get("ess_power_mw", 40) or 40)

        gt_coeffs = self._load_gt_cost_curve(default_linear_cost=gt_cost)
        generators = {}

        for i in range(1, gt_count + 1):
            generators[f"GT{i}"] = GeneratorSpec(
                name=f"GT{i}",
                a=gt_coeffs["a"],
                b=gt_coeffs["b"] + ((i - 1) * 10.0),
                c=gt_coeffs["c"],
                cost_coeff=0.0,
                p_min=gt_min,
                p_max=gt_max,
                ramp_rate=50.0,
            )

        generators["SMR1"] = GeneratorSpec(
            name="SMR1",
            a=0.0,
            b=smr_cost,
            c=0.0,
            cost_coeff=0.0,
            p_min=smr_min,
            p_max=smr_max,
            ramp_rate=0.75,
        )

        ess = {
            "ESS1": StorageSpec(
                name="ESS1",
                capacity_mwh=ess_capacity,
                max_power_mw=ess_power,
                efficiency=0.95,
                initial_soc=0.5,
                min_soc=0.1,
                max_soc=0.9,
                aging_cost=5000.0,
            )
        }

        grid_price_profile = self._build_grid_price_profile(timestamps, T)
        fixed_base_cost = 107866666.0

        params = EDParams(
            is_time_series=True,
            time_steps=T,
            demand_profile=net_demand,
            pv_profile=pv_profile,
            grid_price_profile=grid_price_profile,
            timestamps=timestamps,
            generators=generators,
            ess=ess,
            base_rate=fixed_base_cost,
        )

        state["params"] = params
        print(f"EDParams Created. Steps: {T}, GT count: {gt_count}, fixed base cost: {fixed_base_cost:,.0f} KRW")
        return state

    def _load_gt_cost_curve(self, default_linear_cost):
        gt_coeffs = {"a": 0.0, "b": default_linear_cost, "c": 0.0}
        target_file = "gtfuel.csv"
        exchange_rate = 1300.0

        if not os.path.exists(target_file):
            return gt_coeffs

        try:
            df = pd.read_csv(target_file)
            df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
            power_col = next((c for c in df.columns if "power" in c and "mw" in c), None)
            cost_col = next((c for c in df.columns if "cost" in c and "sec" in c), None)
            if not power_col or not cost_col:
                return gt_coeffs

            x_power = pd.to_numeric(df[power_col], errors="coerce")
            y_cost_sec = pd.to_numeric(df[cost_col], errors="coerce")
            valid_mask = x_power.notnull() & y_cost_sec.notnull()
            if not valid_mask.any():
                return gt_coeffs

            y_cost_krw_15min = y_cost_sec[valid_mask] * exchange_rate * 900.0
            coeffs = np.polyfit(x_power[valid_mask], y_cost_krw_15min, 2)
            return {"a": float(coeffs[0]), "b": float(coeffs[1]), "c": float(coeffs[2])}
        except Exception as exc:
            print(f"GT fuel cost curve skipped: {exc}")
            return gt_coeffs

    def _build_grid_price_profile(self, timestamps, time_steps):
        current_month = 4
        if timestamps:
            try:
                first = timestamps[0]
                if "-" in first:
                    current_month = int(first.split("-")[1])
                elif "/" in first:
                    current_month = int(first.split("/")[0])
            except Exception:
                pass

        summer = {"light": 120000.0, "mid": 190000.0, "peak": 350000.0}
        spring = {"light": 120000.0, "mid": 140000.0, "peak": 280000.0}
        winter = {"light": 125000.0, "mid": 180000.0, "peak": 320000.0}

        if current_month in [6, 7, 8]:
            mode, rates_mwh = "SUMMER", summer
        elif current_month in [11, 12, 1, 2]:
            mode, rates_mwh = "WINTER", winter
        else:
            mode, rates_mwh = "SPRING_FALL", spring

        rates_15min = {key: value / 4.0 for key, value in rates_mwh.items()}
        print(f"Grid TOU mode: {mode}, peak {rates_15min['peak']:,.0f} KRW/15min")

        prices = []
        for i in range(time_steps):
            hour = (9 + int(i / 4)) % 24
            if timestamps:
                try:
                    hour = int(str(timestamps[i]).split(" ")[-1].split(":")[0])
                except Exception:
                    pass

            if hour >= 23 or hour < 9:
                price = rates_15min["light"]
            elif mode == "WINTER":
                if (10 <= hour < 12) or (17 <= hour < 20) or (22 <= hour < 23):
                    price = rates_15min["peak"]
                else:
                    price = rates_15min["mid"]
            elif 10 <= hour < 17:
                price = rates_15min["peak"]
            else:
                price = rates_15min["mid"]
            prices.append(price)
        return prices
