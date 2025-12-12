import pandas as pd
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state.schemas import EDParams, GeneratorSpec, StorageSpec, RenewableSpec
from core.dynamic_solver import solve_dynamic_ed
# from agents.explanation_agent import explain_solution

def run_custom_scenario():
    print(">>> Running Custom Scenario (NO PV CURTAILMENT): 400MW Load + PV must-take + 40MW/160MWh ESS")
    
    # -----------------------------
    # 1. Load Data
    # -----------------------------
    # (1) Load Profile (데이터센터 부하)
    load_path = "datacenter_load/dc_profile_15min_ED.csv"
    if not os.path.exists(load_path):
        load_path = "d:/data_center_ed_agent/datacenter_load/dc_profile_15min_ED.csv"
    
    df_load = pd.read_csv(load_path)
    # power_total_scaled_MW : 15분 단위 데이터센터 부하 [MW]
    demand_profile = df_load["power_total_scaled_MW"].astype(float).tolist()[:96]

    # (2) PV Profile (15분 단위 PV 출력 [MW])
    pv_path = "datacenter_load/pv_profile_15min_ED.csv"
    if not os.path.exists(pv_path):
        pv_path = "d:/data_center_ed_agent/datacenter_load/pv_profile_15min_ED.csv"
    
    df_pv = pd.read_csv(pv_path)
    pv_profile = df_pv["pv_power_MW"].astype(float).tolist()

    # 길이 보정 (하루 96 step)
    if len(pv_profile) < 96:
        pv_profile += [0.0] * (96 - len(pv_profile))
    pv_profile = pv_profile[:96]

    # -----------------------------
    # 2. PV must-take 가정 → 순부하(Net load) 생성
    # -----------------------------
    net_demand_profile = []
    for d, p in zip(demand_profile, pv_profile):
        net = d - p
        # 만약 PV가 load보다 큰 순간이 있어도, ED가 보는 건 "최소 0"의 순부하로 제한
        net_demand_profile.append(max(net, 0.0))

    # 간단한 통계 출력 (검증용)
    total_load_energy = sum(demand_profile) * 0.25   # 15분 → 0.25h
    total_pv_energy   = sum(pv_profile) * 0.25
    total_net_energy  = sum(net_demand_profile) * 0.25

    print("---- Basic Energy Check (15min resolution) ----")
    print(f"Total Load Energy: {total_load_energy:.2f} MWh")
    print(f"Total PV  Energy:  {total_pv_energy:.2f} MWh")
    print(f"Net   Load Energy: {total_net_energy:.2f} MWh")
    print("------------------------------------------------\n")

    # -----------------------------
    # 3. ED Parameters 정의
    #    (PV는 must-take → ED에는 순부하만 제공)
    # -----------------------------
    params = EDParams(
        generators={
            "G1": GeneratorSpec(name="G1", a=0.001, b=0.5, c=3, p_min=100, p_max=300),
            "G2": GeneratorSpec(name="G2", a=0.002, b=0.3, c=5, p_min=150, p_max=300),
        },
        demand=0,
        is_time_series=True,

        # 핵심: ED가 보는 수요는 "순부하"
        demand_profile=net_demand_profile,

        # 여기서는 ED 안에서 PV를 결정변수로 쓰지 않음 → profile/스펙을 비워둔다.
        # (dynamic_solver 구현에 따라 None 또는 [0.0]*96 중 하나 선택)
        # PV profile must be provided if params.pv is set
        pv_profile=pv_profile,
        
        pv_reserve_ratio=0.1, # 10% Required Reserve
        
        ess={
            "ESS1": StorageSpec(
                name="ESS1",
                capacity_mwh=160.0,   # 160 MWh
                max_power_mw=40.0,    # 40 MW
                efficiency=0.95,
                initial_soc=0.5,
                min_soc=0.1,
                max_soc=0.9,
                aging_cost=10.0       # [Added] Aging Cost
            )
        },

        # --- PV CUSTOM SPEC ---
        pv={
            "PV1": RenewableSpec(
                name="PV1",
                peak_mw=1.0, 
                curtailment_cost=0.0
            )
        }
    )

    # -----------------------------
    # 4. Solve
    # -----------------------------
    print(">>> Solving Dynamic ED (Pyomo) on NET LOAD (Load - PV)...")
    sol = solve_dynamic_ed(params)
    
    # -----------------------------
    # 5. 결과 요약 출력
    # -----------------------------
    print("\n================ RESULT SUMMARY ==================")
    print("Scenario: 400MW Data Center Load, PV must-take (net load = load - PV), ESS 40MW/160MWh")
    print(f"Total Fuel Cost (G1+G2+기타): {sol.cost:,.2f} $")
    print(f"Solver Status: {sol.note}")
    
    if sol.ess_schedule:
        ess = sol.ess_schedule["ESS1"]
        print("\n[ESS Operation]")
        print(f"Total Charged:    {sum(ess['charge'])*0.25:.2f} MWh")
        print(f"Total Discharged: {sum(ess['discharge'])*0.25:.2f} MWh")
        print(f"Final SoC:        {ess['soc'][-1]:.2f} MWh (Initial: {80.0:.2f} MWh)")
        
        disfunctions = [x for x in ess['discharge'] if x > 0.1]
        if disfunctions:
            print(f"Discharge Events: {len(disfunctions)} intervals (active peak shaving)")
    else:
        print("No ESS Schedule found (Optimization might have failed or ESS unused)")
    
    print("==================================================")

if __name__ == "__main__":
    run_custom_scenario()
