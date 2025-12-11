
import pandas as pd
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state.schemas import EDParams, GeneratorSpec, StorageSpec, RenewableSpec
from core.dynamic_solver import solve_dynamic_ed
# from agents.explanation_agent import explain_solution (Skipped to avoid API Key requirement for test)

def run_custom_scenario():
    print(">>> Running Custom Scenario: 400MW Load + 60MW PV + 40MW/160MWh ESS")
    
    # 1. Load Data
    # Load Profile
    load_path = "datacenter_load/dc_profile_15min_ED.csv"
    if not os.path.exists(load_path):
        load_path = "d:/data_center_ed_agent/datacenter_load/dc_profile_15min_ED.csv"
    
    df_load = pd.read_csv(load_path)
    # Scale load if necessary? The file header says 'power_total_scaled_MW'.
    demand_profile = df_load["power_total_scaled_MW"].astype(float).tolist()[:96]
    
    # PV Profile
    pv_path = "datacenter_load/pv_profile_15min_ED.csv"
    if not os.path.exists(pv_path):
        pv_path = "d:/data_center_ed_agent/datacenter_load/pv_profile_15min_ED.csv"
    
    df_pv = pd.read_csv(pv_path)
    pv_profile = df_pv["pv_power_MW"].astype(float).tolist()
    
    # Pad to 96 if short
    if len(pv_profile) < 96:
        pv_profile += [0.0] * (96 - len(pv_profile))
    pv_profile = pv_profile[:96]

    # 2. Define Parameters
    params = EDParams(
        generators={
            "G1": GeneratorSpec(name="G1", a=0.001, b=0.5, c=3, p_min=100, p_max=300),
            "G2": GeneratorSpec(name="G2", a=0.002, b=0.3, c=5, p_min=150, p_max=300),
        },
        demand=0, 
        is_time_series=True,
        demand_profile=demand_profile,
        pv_profile=pv_profile,
        
        # --- ESS CUSTOM SPEC ---
        ess={
            "ESS1": StorageSpec(
                name="ESS1",
                capacity_mwh=160.0,   # 160 MWh
                max_power_mw=40.0,    # 40 MW
                efficiency=0.95,
                initial_soc=0.5,
                min_soc=0.1,
                max_soc=0.9
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

    # 3. Solve
    print(">>> Solving Dynamic ED (Pyomo)...")
    sol = solve_dynamic_ed(params)
    
    # 4. Results
    print("\n================ RESULT SUMMARY ==================")
    print(f"Scenario: 400MW Load, PV Profile (Peak ~56MW), ESS (40MW/160MWh)")
    print(f"Total Fuel Cost: {sol.cost:,.2f} $")
    print(f"Solver Status: {sol.note}")
    
    if sol.ess_schedule:
        ess = sol.ess_schedule["ESS1"]
        print("\n[ESS Operation]")
        print(f"Total Charged:    {sum(ess['charge'])*0.25:.2f} MWh")
        print(f"Total Discharged: {sum(ess['discharge'])*0.25:.2f} MWh")
        print(f"Final SoC:        {ess['soc'][-1]:.2f} MWh (Initial: {80.0:.2f} MWh)")
        
        # Simple analysis of peak discharge
        disfunctions = [x for x in ess['discharge'] if x > 0.1]
        if disfunctions:
            print(f"Discharge Events: {len(disfunctions)} intervals (active peak shaving)")
    else:
        print("No ESS Schedule found (Optimization might have failed or ESS unused)")

    print("==================================================")

if __name__ == "__main__":
    run_custom_scenario()
