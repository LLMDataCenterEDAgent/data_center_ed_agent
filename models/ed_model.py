# models/ed_model.py
from pyomo.environ import (
    ConcreteModel, Var, Constraint, Objective,
    NonNegativeReals, RangeSet, minimize
)


def build_ed_model(data, config):

    m = ConcreteModel()
    m.T = RangeSet(1, data["T"])

    m.P_grid = Var(m.T, domain=NonNegativeReals)
    m.P_pv   = Var(m.T, domain=NonNegativeReals)
    m.P_mgt  = Var(m.T, domain=NonNegativeReals)
    m.P_smr  = Var(m.T, domain=NonNegativeReals)
    m.P_ch   = Var(m.T, domain=NonNegativeReals)
    m.P_dis  = Var(m.T, domain=NonNegativeReals)
    m.SOC    = Var(m.T, domain=NonNegativeReals)

    # Objective
    def obj(m):
        return sum(
            data["c_grid"][t] * m.P_grid[t] +
            data["c_mgt"] * m.P_mgt[t] +
            data["c_smr"] * m.P_smr[t]
            for t in m.T
        )
    m.OBJ = Objective(rule=obj, sense=minimize)

    # Power balance
    def power(m, t):
        return (
            m.P_grid[t] + m.P_pv[t] + m.P_mgt[t] +
            m.P_smr[t] + m.P_dis[t] - m.P_ch[t]
            == data["load"][t]
        )
    m.PowerBalance = Constraint(m.T, rule=power)

    # SOC
    eta_ch = data["eta_ch"]
    eta_dis = data["eta_dis"]

    def soc(m, t):
        if t == 1:
            return m.SOC[t] == data["soc_init"]
        return (
            m.SOC[t] ==
            m.SOC[t-1] +
            eta_ch * m.P_ch[t-1] -
            (1/eta_dis) * m.P_dis[t-1]
        )
    m.SOC_Update = Constraint(m.T, rule=soc)

    def soc_bnd(m, t):
        return m.SOC[t] <= data["E_max"]
    m.SOC_Limit = Constraint(m.T, rule=soc_bnd)

    # PV limit
    def pv_lim(m, t):
        return m.P_pv[t] <= data["pv_avail"][t]
    m.PV_Limit = Constraint(m.T, rule=pv_lim)

    # MGT
    if config["use_mgt"]:
        ru = data["ramp_up_mgt"]
        rd = data["ramp_down_mgt"]

        def up(m, t):
            if t == 1: return Constraint.Skip
            return m.P_mgt[t] - m.P_mgt[t-1] <= ru

        def down(m, t):
            if t == 1: return Constraint.Skip
            return m.P_mgt[t-1] - m.P_mgt[t] <= rd

        m.MGT_Up = Constraint(m.T, rule=up)
        m.MGT_Down = Constraint(m.T, rule=down)
    else:
        def mgt_off(m, t): return m.P_mgt[t] == 0
        m.MGT_Off = Constraint(m.T, rule=mgt_off)

    # SMR
    if config["use_smr"]:
        def smr_min(m, t): return m.P_smr[t] >= data["p_smr_min"]
        def smr_max(m, t): return m.P_smr[t] <= data["p_smr_max"]
        m.SMR_Min = Constraint(m.T, rule=smr_min)
        m.SMR_Max = Constraint(m.T, rule=smr_max)
    else:
        def smr_off(m, t): return m.P_smr[t] == 0
        m.SMR_Off = Constraint(m.T, rule=smr_off)

    return m


def model_builder_node(state):
    state["model"] = build_ed_model(
        state["data_dict"],
        state["constraint_config"]
    )
    return state