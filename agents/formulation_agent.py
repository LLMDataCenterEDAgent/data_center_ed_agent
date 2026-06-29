# agents/formulation_agent.py

import os
import re
import json
import math

import numpy as np
import pandas as pd

from state.base_state import AgentState
from state.schemas import EDParams, GeneratorSpec, StorageSpec
from utils.json_cleaner import extract_json_like
from utils.parser_prompt import SCENARIO_PARSER_SYSTEM_PROMPT
from utils.runtime_secrets import load_streamlit_secrets_into_env


class FormulationAgent:
    # Keys the natural-language parser is allowed to emit (must match scenario_config).
    _ALLOWED_KEYS = {
        "gt_count", "gt_min", "gt_max", "gt_cost",
        "smr_min", "smr_max", "smr_cost",
        "ess_capacity_mwh", "ess_power_mw", "grid_import_limit_mw",
        "tariff_season",
        "interval_minutes", "time_steps", "start_row",
    }

    # TOU tariff season aliases -> canonical season understood by the price model.
    _SEASON_ALIASES = {
        "summer": "summer", "여름": "summer",
        "winter": "winter", "겨울": "winter",
        "spring": "spring_fall", "fall": "spring_fall", "autumn": "spring_fall",
        "spring_fall": "spring_fall", "spring/fall": "spring_fall",
        "봄": "spring_fall", "가을": "spring_fall",
    }

    # Keys for which a non-positive value is never meaningful and should be
    # ignored (letting the form/defaults supply the value instead).
    _POSITIVE_ONLY_KEYS = {
        "gt_count", "gt_min", "gt_max", "gt_cost",
        "smr_min", "smr_max", "smr_cost",
        "ess_capacity_mwh", "ess_power_mw",
        "interval_minutes", "time_steps",
    }

    # Synonym normalisation: map free-form resource names onto the canonical
    # GT / SMR / ESS tokens so the parser assigns the correct cost functions.
    _SYNONYM_RULES = [
        (r"combustion turbines?", "GT"),
        (r"gas turbines?", "GT"),
        (r"가스\s*터빈", "GT"),
        (r"small\s+modular\s+reactors?", "SMR"),
        (r"nuclear\s+reactors?", "SMR"),
        (r"소형\s*모듈\s*원자로", "SMR"),
        (r"원자력", "SMR"),
        (r"원자로", "SMR"),
        (r"battery\s+energy\s+storage(?:\s+system)?", "ESS"),
        (r"energy\s+storage\s+systems?", "ESS"),
        (r"batter(?:y|ies)", "ESS"),
        (r"배터리", "ESS"),
        (r"에너지\s*저장\s*장치", "ESS"),
    ]

    def _normalize_synonyms(self, text):
        if not text:
            return ""
        normalized = text
        for pattern, replacement in self._SYNONYM_RULES:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        return normalized

    def _normalize_season(self, value):
        if value is None:
            return None
        key = str(value).strip().lower().replace(" ", "_")
        return self._SEASON_ALIASES.get(key)

    def _extract_params_from_nl(self, problem_text, current_config=None):
        """(i) Syntactic-repair + LLM parse of the operator's request.

        The current scenario is supplied to the LLM as JSON context so that
        relative requests (e.g. "add one gas turbine") resolve against it.
        Returns a dict of changed scenario parameters, or {} when no
        natural-language request is present or the LLM call fails.
        """
        text = self._normalize_synonyms(problem_text or "")
        if not text.strip():
            return {}
        context = {
            k: current_config.get(k)
            for k in self._ALLOWED_KEYS
            if current_config and current_config.get(k) is not None
        }
        user_msg = (
            f"Current scenario (JSON):\n{json.dumps(context)}\n\n"
            f"User request:\n{text}"
        )
        try:
            from openai import OpenAI

            load_streamlit_secrets_into_env()
            client = OpenAI()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SCENARIO_PARSER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
            )
            content = resp.choices[0].message.content or "{}"
            parsed = extract_json_like(content)
            if not isinstance(parsed, dict):
                return {}
            result = {}
            for key, value in parsed.items():
                if key not in self._ALLOWED_KEYS or value is None:
                    continue
                if key == "tariff_season":
                    season = self._normalize_season(value)
                    if season:
                        result[key] = season
                    continue
                # Drop non-positive values the LLM sometimes invents for
                # unspecified ranges, so they fall back to form/defaults
                # (grid_import_limit_mw and start_row may legitimately be 0).
                if key in self._POSITIVE_ONLY_KEYS:
                    try:
                        if float(value) <= 0:
                            continue
                    except (TypeError, ValueError):
                        continue
                result[key] = value
            return result
        except Exception as exc:
            print(f"[Formulation] NL extraction skipped: {exc}")
            return {}

    def run(self, state: AgentState) -> AgentState:
        print("\n--- Formulation Agent Started (Streamlit Scenario + TOU Cost) ---")

        previous_solver_error = state.get("solver_error")
        if previous_solver_error:
            attempt = int(state.get("correction_attempts", 0) or 0) + 1
            state["correction_attempts"] = attempt
            print(f">>> Self-correction attempt {attempt}: {previous_solver_error}")

        raw_config = dict(state.get("scenario_config") or {})
        # Parse the operator's natural-language request into parameters on the
        # first pass only; self-correction retries reuse the merged config.
        if not previous_solver_error:
            nl_params = self._extract_params_from_nl(state.get("problem_text"), raw_config)
            if nl_params:
                print(f">>> NL-extracted scenario params (override form/defaults): {nl_params}")
                raw_config.update(nl_params)

        scenario_config = self._sanitize_config(raw_config, state)
        data = state.get("parsed_data")
        interval_minutes = int(scenario_config.get("interval_minutes", 15) or 15)
        interval_hours = interval_minutes / 60.0

        if not data:
            fallback_steps = int(scenario_config.get("time_steps", max(1, int(24 / interval_hours))) or 96)
            net_demand = [300.0] * fallback_steps
            pv_profile = [0.0] * fallback_steps
            timestamps = None
        else:
            net_demand = data["net_demand_profile"]
            pv_profile = data["pv_profile"]
            timestamps = data.get("timestamps")
            interval_minutes = int(data.get("interval_minutes", interval_minutes) or interval_minutes)
            interval_hours = interval_minutes / 60.0

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
        grid_import_limit = scenario_config.get("grid_import_limit_mw")

        gt_coeffs = self._load_gt_cost_curve(default_linear_cost=gt_cost, interval_hours=interval_hours)
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

        grid_price_profile = self._build_grid_price_profile(
            timestamps, T, interval_hours,
            season_override=scenario_config.get("tariff_season"),
        )
        fixed_base_cost = 107866666.0

        params = EDParams(
            is_time_series=True,
            time_steps=T,
            demand_profile=net_demand,
            interval_minutes=interval_minutes,
            interval_hours=interval_hours,
            pv_profile=pv_profile,
            grid_price_profile=grid_price_profile,
            timestamps=timestamps,
            grid_import_limit_mw=grid_import_limit,
            generators=generators,
            ess=ess,
            base_rate=fixed_base_cost,
        )

        state["solver_error"] = None
        state["scenario_config"] = scenario_config
        state["params"] = params
        print(f"EDParams Created. Steps: {T}, GT count: {gt_count}, fixed base cost: {fixed_base_cost:,.0f} KRW")
        return state

    def _sanitize_config(self, scenario_config, state):
        config = dict(scenario_config)
        errors = []

        def numeric(key, default, minimum=None):
            raw = config.get(key, default)
            try:
                value = float(raw)
            except (TypeError, ValueError):
                errors.append(f"{key}={raw!r} is not numeric; replaced with {default}.")
                value = float(default)

            if not math.isfinite(value):
                errors.append(f"{key} is not finite; replaced with {default}.")
                value = float(default)

            if minimum is not None and value < minimum:
                errors.append(f"{key}={value} is below {minimum}; clipped.")
                value = float(minimum)

            config[key] = value
            return value

        gt_count_raw = config.get("gt_count", 2)
        try:
            gt_count = int(gt_count_raw)
        except (TypeError, ValueError):
            errors.append(f"gt_count={gt_count_raw!r} is invalid; replaced with 2.")
            gt_count = 2
        config["gt_count"] = max(1, gt_count)

        interval_raw = config.get("interval_minutes", 15)
        try:
            interval_minutes = int(interval_raw)
        except (TypeError, ValueError):
            interval_minutes = 15
            errors.append(f"interval_minutes={interval_raw!r} is invalid; replaced with 15.")
        if interval_minutes not in (15, 30, 60):
            errors.append(f"interval_minutes={interval_minutes} is unsupported; replaced with 15.")
            interval_minutes = 15
        config["interval_minutes"] = interval_minutes

        numeric("gt_min", 85, 0.0)
        numeric("gt_max", 170, 0.0)
        numeric("gt_cost", 0.03, 0.0)
        numeric("smr_min", 91, 0.0)
        numeric("smr_max", 121, 0.0)
        numeric("smr_cost", 2500, 0.0)
        numeric("ess_capacity_mwh", 160, 0.0)
        numeric("ess_power_mw", 40, 0.0)
        numeric("grid_relax_step_mw", 30, 0.0)

        raw_grid_limit = config.get("grid_import_limit_mw")
        if raw_grid_limit in ("", None, "unbounded", "none", "None"):
            config["grid_import_limit_mw"] = None
        else:
            try:
                grid_limit = float(raw_grid_limit)
                if not math.isfinite(grid_limit) or grid_limit < 0:
                    errors.append(f"grid_import_limit_mw={raw_grid_limit!r} is invalid; treated as unbounded.")
                    grid_limit = None
                config["grid_import_limit_mw"] = grid_limit
            except (TypeError, ValueError):
                errors.append(f"grid_import_limit_mw={raw_grid_limit!r} is invalid; treated as unbounded.")
                config["grid_import_limit_mw"] = None

        for min_key, max_key in [("gt_min", "gt_max"), ("smr_min", "smr_max")]:
            if config[min_key] > config[max_key]:
                errors.append(f"{min_key} exceeded {max_key}; swapped bounds.")
                config[min_key], config[max_key] = config[max_key], config[min_key]

        if state.get("solver_error"):
            # Conservative repair used after a solver failure. It keeps the user
            # scenario recognizable while removing common infeasibility triggers.
            config["gt_min"] = min(config["gt_min"], config["gt_max"])
            config["smr_min"] = min(config["smr_min"], config["smr_max"])
            config["ess_power_mw"] = min(config["ess_power_mw"], config["ess_capacity_mwh"] * 4.0) if config["ess_capacity_mwh"] else 0.0
            if config.get("grid_import_limit_mw") is not None:
                attempt = int(state.get("correction_attempts", 0) or 0)
                if attempt >= 2:
                    errors.append("grid_import_limit_mw remained binding; relaxed to unbounded.")
                    config["grid_import_limit_mw"] = None
                else:
                    step = float(config.get("grid_relax_step_mw", 30.0) or 30.0)
                    old_limit = float(config["grid_import_limit_mw"])
                    config["grid_import_limit_mw"] = old_limit + step
                    errors.append(
                        f"grid_import_limit_mw relaxed from {old_limit:.1f} to {config['grid_import_limit_mw']:.1f} MW."
                    )

        state["validation_errors"] = errors
        if errors:
            print(">>> Formulation validation repairs:")
            for err in errors:
                print(f" - {err}")
        return config

    def _load_gt_cost_curve(self, default_linear_cost, interval_hours=0.25):
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

            interval_seconds = interval_hours * 3600.0
            y_cost_krw_interval = y_cost_sec[valid_mask] * exchange_rate * interval_seconds
            coeffs = np.polyfit(x_power[valid_mask], y_cost_krw_interval, 2)
            return {"a": float(coeffs[0]), "b": float(coeffs[1]), "c": float(coeffs[2])}
        except Exception as exc:
            print(f"GT fuel cost curve skipped: {exc}")
            return gt_coeffs

    def _build_grid_price_profile(self, timestamps, time_steps, interval_hours=0.25, season_override=None):
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
        season_modes = {
            "summer": ("SUMMER", summer),
            "winter": ("WINTER", winter),
            "spring_fall": ("SPRING_FALL", spring),
        }

        # An explicit tariff_season (from the request) overrides the date-based season.
        season = self._normalize_season(season_override)
        if season in season_modes:
            mode, rates_mwh = season_modes[season]
        elif current_month in [6, 7, 8]:
            mode, rates_mwh = "SUMMER", summer
        elif current_month in [11, 12, 1, 2]:
            mode, rates_mwh = "WINTER", winter
        else:
            mode, rates_mwh = "SPRING_FALL", spring

        rates_interval = {key: value * interval_hours for key, value in rates_mwh.items()}
        interval_minutes = int(interval_hours * 60)
        print(f"Grid TOU mode: {mode}, peak {rates_interval['peak']:,.0f} KRW/{interval_minutes}min")

        prices = []
        for i in range(time_steps):
            hour = (9 + int(i / 4)) % 24
            if timestamps:
                try:
                    hour = int(str(timestamps[i]).split(" ")[-1].split(":")[0])
                except Exception:
                    pass

            if hour >= 23 or hour < 9:
                price = rates_interval["light"]
            elif mode == "WINTER":
                if (10 <= hour < 12) or (17 <= hour < 20) or (22 <= hour < 23):
                    price = rates_interval["peak"]
                else:
                    price = rates_interval["mid"]
            elif 10 <= hour < 17:
                price = rates_interval["peak"]
            else:
                price = rates_interval["mid"]
            prices.append(price)
        return prices
