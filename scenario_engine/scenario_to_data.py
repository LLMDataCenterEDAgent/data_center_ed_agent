# scenario_engine/scenario_to_data.py

def scenario_to_data(scenario):

    T = scenario["hours"]
    load = scenario["load_curve"]
    pv = scenario["pv_profile"]
    ess = scenario["ess"]

    return {
        "T": T,
        "load": {t+1: load[t] for t in range(T)},
        "pv_avail": {t+1: pv[t] for t in range(T)},
        "eta_ch": ess["eta_ch"],
        "eta_dis": ess["eta_dis"],
        "E_max": ess["E_max"],
        "soc_init": ess["soc_init"],
        "dt": 1,
        "c_grid": {t+1: 0.15 for t in range(T)},
        "c_mgt": 0.20,
        "c_smr": 0.05,
        "ramp_up_mgt": 20,
        "ramp_down_mgt": 20,
        "p_smr_min": 50,
        "p_smr_max": 100
    }


def data_dict_node(state):
    state["data_dict"] = scenario_to_data(state["scenario"])
    return state