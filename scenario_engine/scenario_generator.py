# scenario_engine/scenario_generator.py
import numpy as np

def generate_scenario():

    hours = 24

    cpu_usage = np.clip(np.random.normal(0.6, 0.1, hours), 0.2, 0.95)
    load_curve = (cpu_usage * 300).tolist()

    pv_peak = 80
    pv_profile = [max(0, pv_peak * np.sin((i - 6) / 12 * np.pi)) for i in range(hours)]

    ess = {
        "E_max": 200,
        "soc_init": 100,
        "eta_ch": 0.95,
        "eta_dis": 0.95
    }

    return {
        "hours": hours,
        "load_curve": load_curve,
        "pv_profile": pv_profile,
        "ess": ess
    }


def scenario_node(state):
    state["scenario"] = generate_scenario()
    return state