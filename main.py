# main.py

import os
import re
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF, XPos, YPos
from workflow.graph import build_graph


def classify_generator(name):
    upper_name = name.upper()
    if "SMR" in upper_name or "NUC" in upper_name:
        return "SMR"
    if "GT" in upper_name or "GAS" in upper_name:
        return "GT"
    return "OTHER"


def calc_generator_cost(spec, power):
    if spec.a != 0 or spec.b != 0 or spec.c != 0:
        return spec.a * power ** 2 + spec.b * power + spec.c
    if getattr(spec, "cost_coeff", 0):
        return power * spec.cost_coeff
    return 0.0


def normalize_explanation_text(text):
    if not text:
        return ""

    cleaned_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("!["):
            continue
        line = re.sub(r"^#+\s*", "", line)
        line = line.replace("**", "").replace("*", "")
        line = line.replace("`", "")
        line = re.sub(r"^\d+\.\s*", "", line)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def build_report_metrics(solution_data, params):
    gen_names = list(params.generators.keys())
    ess_names = list(params.ess.keys()) if params.ess else []
    time_indices = range(params.time_steps)

    gt_names = [g for g in gen_names if classify_generator(g) == "GT"]
    smr_names = [g for g in gen_names if classify_generator(g) == "SMR"]

    total_cost = float(solution_data.get("Total_Cost", 0.0))
    fixed_cost = float(getattr(params, "base_rate", 0.0) or 0.0)
    variable_cost = total_cost - fixed_cost

    smr_cost = 0.0
    gt_cost = 0.0
    total_pv_energy_mwh = 0.0
    total_ess_discharge_mwh = 0.0

    for t in time_indices:
        row = solution_data.get(t, {})
        total_pv_energy_mwh += row.get("P_PV", 0.0) * 0.25
        for g in gt_names:
            gt_cost += calc_generator_cost(params.generators[g], row.get(f"P_{g}", 0.0))
        for g in smr_names:
            smr_cost += calc_generator_cost(params.generators[g], row.get(f"P_{g}", 0.0))
        for e in ess_names:
            total_ess_discharge_mwh += row.get(f"P_dis_{e}", 0.0) * 0.25

    prices = params.grid_price_profile if params.grid_price_profile else [0.0] * params.time_steps
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

    tou_order = ["Off-Peak", "Mid-Peak", "On-Peak", "Flat"]
    tou_stats = {
        label: {"count": 0, "SMR": 0.0, "GT": 0.0, "PV": 0.0, "ESS": 0.0, "SOC": 0.0}
        for label in tou_order
    }

    for t in time_indices:
        row = solution_data.get(t, {})
        label = tou_map.get(prices[t], "Flat")
        tou_stats[label]["count"] += 1
        tou_stats[label]["SMR"] += sum(row.get(f"P_{g}", 0.0) for g in smr_names)
        tou_stats[label]["GT"] += sum(row.get(f"P_{g}", 0.0) for g in gt_names)
        tou_stats[label]["PV"] += row.get("P_PV", 0.0)
        tou_stats[label]["ESS"] += sum(row.get(f"P_dis_{e}", 0.0) for e in ess_names)
        tou_stats[label]["SOC"] += sum(row.get(f"SOC_{e}", 0.0) for e in ess_names)

    tou_summary = []
    for label in tou_order:
        stat = tou_stats[label]
        if stat["count"] == 0:
            continue
        tou_summary.append({
            "label": label,
            "smr_mw": stat["SMR"] / stat["count"],
            "gt_mw": stat["GT"] / stat["count"],
            "pv_mw": stat["PV"] / stat["count"],
            "ess_mw": stat["ESS"] / stat["count"],
            "ess_soc_mwh": stat["SOC"] / stat["count"] if ess_names else 0.0,
        })

    total_smr_avg = sum(item["smr_mw"] for item in tou_summary) / len(tou_summary) if tou_summary else 0.0
    total_gt_avg = sum(item["gt_mw"] for item in tou_summary) / len(tou_summary) if tou_summary else 0.0
    total_pv_avg = sum(item["pv_mw"] for item in tou_summary) / len(tou_summary) if tou_summary else 0.0
    total_ess_avg = sum(item["ess_mw"] for item in tou_summary) / len(tou_summary) if tou_summary else 0.0

    total_gt_energy_mwh = total_gt_avg * 24.0
    total_smr_energy_mwh = total_smr_avg * 24.0
    analysis_hours = 24.0

    baseload_ratio = (smr_cost / total_cost * 100.0) if total_cost else 0.0
    variable_ratio = (variable_cost / total_cost * 100.0) if total_cost else 0.0

    gt_capacity_mw = sum(params.generators[g].p_max for g in gt_names)
    smr_capacity_mw = sum(params.generators[g].p_max for g in smr_names)
    pv_capacity_mw = max(params.pv_profile) if params.pv_profile else 0.0
    ess_power_mw = sum(params.ess[e].max_power_mw for e in ess_names) if ess_names else 0.0
    ess_capacity_mwh = sum(params.ess[e].capacity_mwh for e in ess_names) if ess_names else 0.0

    gt_capacity_factor = (total_gt_avg / gt_capacity_mw * 100.0) if gt_capacity_mw else 0.0
    smr_capacity_factor = (total_smr_avg / smr_capacity_mw * 100.0) if smr_capacity_mw else 0.0
    pv_capacity_factor = (total_pv_energy_mwh / (pv_capacity_mw * analysis_hours) * 100.0) if pv_capacity_mw else 0.0
    ess_capacity_factor = (total_ess_discharge_mwh / (ess_power_mw * analysis_hours) * 100.0) if ess_power_mw else 0.0

    return {
        "pv_capacity_mw": pv_capacity_mw,
        "gt_capacity_mw": gt_capacity_mw,
        "smr_capacity_mw": smr_capacity_mw,
        "ess_power_mw": ess_power_mw,
        "ess_capacity_mwh": ess_capacity_mwh,
        "baseload_generation_cost": smr_cost,
        "fixed_cost": fixed_cost,
        "variable_cost": variable_cost,
        "total_cost": total_cost,
        "baseload_ratio": baseload_ratio,
        "variable_ratio": variable_ratio,
        "smr_avg_mw": total_smr_avg,
        "gt_avg_mw": total_gt_avg,
        "pv_avg_mw": total_pv_avg,
        "pv_energy_mwh": total_pv_energy_mwh,
        "ess_avg_mw": total_ess_avg,
        "ess_energy_mwh": total_ess_discharge_mwh,
        "smr_capacity_factor": smr_capacity_factor,
        "gt_capacity_factor": gt_capacity_factor,
        "pv_capacity_factor": pv_capacity_factor,
        "ess_capacity_factor": ess_capacity_factor,
        "tou_summary": tou_summary,
    }


def add_report_line(pdf, font_name, text, indent=0, bold=False, size=10, gap_after=1.5):
    style = "B" if bold and font_name != "KoreanFont" else ""
    pdf.set_x(10 + indent)
    pdf.set_font(font_name, style, size)
    pdf.multi_cell(190 - indent, 5.5, text)
    if gap_after:
        pdf.ln(gap_after)


def render_llm_report(pdf, font_name, explanation_text):
    if not explanation_text or "Error generating explanation." in explanation_text:
        return False

    cleaned_lines = [line.strip() for line in explanation_text.splitlines()]
    cleaned_lines = [line for line in cleaned_lines if line]
    expected_heading = "1. Executive Summary"
    if not any(line.startswith(expected_heading) for line in cleaned_lines):
        return False

    for line in cleaned_lines:
        is_heading = bool(re.match(r"^\d+\.\s+", line))
        indent = 0 if is_heading else 4
        size = 12 if is_heading else 10
        add_report_line(pdf, font_name, line, indent=indent, bold=is_heading, size=size, gap_after=1.5 if is_heading else 1.0)
    return True


def render_structured_report(pdf, font_name, metrics, explanation_text):
    cleaned_explanation = normalize_explanation_text(explanation_text)
    explanation_lines = [line for line in cleaned_explanation.splitlines() if line]

    tou_summary = metrics["tou_summary"]
    peak_slot = next((item for item in tou_summary if item["label"] == "On-Peak"), None)
    offpeak_slot = next((item for item in tou_summary if item["label"] == "Off-Peak"), None)
    if peak_slot is None:
        peak_slot = {"gt_mw": 0.0, "pv_mw": 0.0, "ess_mw": 0.0, "ess_soc_mwh": 0.0}
    if offpeak_slot is None:
        offpeak_slot = {"gt_mw": 0.0, "pv_mw": 0.0, "ess_mw": 0.0, "ess_soc_mwh": 0.0}

    peak_ess_text = "ESS contribution was limited during on-peak hours."
    if peak_slot and peak_slot["ess_mw"] > 0.1:
        peak_ess_text = (
            f"ESS supported peak shaving at {peak_slot['ess_mw']:.1f} MW on average during on-peak hours, "
            f"with average stored energy around {peak_slot['ess_soc_mwh']:.1f} MWh."
        )

    grid_dependency_text = (
        f"SMR baseload capacity of {metrics['smr_capacity_mw']:.1f} MW and PV capacity of {metrics['pv_capacity_mw']:.1f} MW "
        "should be treated as the primary low-cost supply block for daily operation."
    )
    if peak_slot and peak_slot["gt_mw"] > metrics["gt_avg_mw"]:
        grid_dependency_text = (
            f"GT dispatch rises to {peak_slot['gt_mw']:.1f} MW on average during on-peak hours, "
            "which indicates thermal flexibility remains important for peak-period reliability."
        )

    offpeak_charge_text = "Off-peak charging opportunity should be reviewed together with TOU price windows."
    if offpeak_slot:
        offpeak_charge_text = (
            f"During off-peak hours, the system operated around SMR {offpeak_slot['smr_mw']:.1f} MW, "
            f"GT {offpeak_slot['gt_mw']:.1f} MW, and PV {offpeak_slot['pv_mw']:.1f} MW, "
            "which can be used as the reference condition for charging and reserve planning."
        )

    executive_summary_1 = (
        f"This report evaluates a microgrid portfolio composed of PV {metrics['pv_capacity_mw']:.1f} MW, "
        f"GT {metrics['gt_capacity_mw']:.1f} MW, SMR {metrics['smr_capacity_mw']:.1f} MW, and ESS "
        f"{metrics['ess_power_mw']:.1f} MW / {metrics['ess_capacity_mwh']:.1f} MWh over a 24-hour horizon. "
        f"The optimization outcome indicates a portfolio centered on stable nuclear baseload, flexible gas support, "
        f"daytime renewable injection, and targeted storage discharge during expensive periods."
    )
    executive_summary_2 = (
        f"Total cost reached {metrics['total_cost']:,.0f} KRW, of which baseload generation cost accounted for "
        f"{metrics['baseload_generation_cost']:,.0f} KRW ({metrics['baseload_ratio']:.1f}%) and variable operating cost "
        f"accounted for {metrics['variable_cost']:,.0f} KRW ({metrics['variable_ratio']:.1f}%). "
        f"This indicates that short-term operational improvement is primarily determined by dispatch strategy, especially "
        f"GT output management and on-peak grid substitution."
    )

    system_config_1 = (
        f"The asset portfolio combines a high-stability source, SMR ({metrics['smr_capacity_mw']:.1f} MW), with high-flexibility "
        f"GT capacity ({metrics['gt_capacity_mw']:.1f} MW), medium-scale PV ({metrics['pv_capacity_mw']:.1f} MW), and "
        f"an ESS sized at {metrics['ess_power_mw']:.1f} MW / {metrics['ess_capacity_mwh']:.1f} MWh. "
        "From a strategic perspective, this mix is balanced toward reliability first, while still preserving opportunities "
        "for renewable integration and time-shifting."
    )
    system_config_2 = (
        "The portfolio shows a deliberate separation of roles: SMR provides stable baseload, GT covers residual demand and "
        "ramping needs, PV offsets daytime energy, and ESS supports temporal balancing. This is a typical hybrid architecture "
        "for data center-class loads, where operational continuity and peak management are both critical."
    )

    cost_structure_1 = (
        f"Cost decomposition shows that variable cost dominates the total economic outcome. Baseload generation cost "
        f"contributes {metrics['baseload_ratio']:.1f}% of total cost, while variable cost contributes {metrics['variable_ratio']:.1f}%. "
        "This confirms that the optimization problem is governed more by dispatch responsiveness than by fixed portfolio ownership."
    )
    cost_structure_2 = (
        f"In practical terms, this means cost efficiency depends on limiting GT-intensive and grid-dependent operation during high-price "
        f"intervals. Even though SMR is a large-capacity asset, its cost contribution remains comparatively stable, while daily variability "
        f"is driven by GT, PV availability, and ESS utilization."
    )

    dispatch_intro = (
        "Generation-source analysis confirms that each resource was assigned a differentiated operating role consistent with its technical and economic characteristics."
    )

    add_report_line(pdf, font_name, "1. Executive Summary", bold=True, size=12)
    add_report_line(pdf, font_name, executive_summary_1, indent=4)
    add_report_line(pdf, font_name, executive_summary_2, indent=4, gap_after=3)

    add_report_line(pdf, font_name, "2. System Configuration Analysis", bold=True, size=12)
    add_report_line(pdf, font_name, system_config_1, indent=4)
    add_report_line(pdf, font_name, system_config_2, indent=4, gap_after=3)

    add_report_line(pdf, font_name, "3. Cost Structure Analysis", bold=True, size=12)
    add_report_line(pdf, font_name, cost_structure_1, indent=4)
    add_report_line(pdf, font_name, cost_structure_2, indent=4, gap_after=3)

    add_report_line(pdf, font_name, "4. Dispatch Strategy Analysis by Generation Source", bold=True, size=12)
    add_report_line(pdf, font_name, dispatch_intro, indent=4)
    add_report_line(pdf, font_name, f"- SMR: Average output {metrics['smr_avg_mw']:.1f} MW with capacity factor {metrics['smr_capacity_factor']:.1f}% over 24 hours. It functioned as the dominant baseload source with high stability and low short-term variability.", indent=6)
    add_report_line(pdf, font_name, f"- GT: Average output {metrics['gt_avg_mw']:.1f} MW with capacity factor {metrics['gt_capacity_factor']:.1f}%. GT served as the flexible thermal resource, absorbing residual demand and supporting peak conditions.", indent=6)
    add_report_line(pdf, font_name, f"- PV: Average output {metrics['pv_avg_mw']:.1f} MW, total energy {metrics['pv_energy_mwh']:.1f} MWh, and capacity factor {metrics['pv_capacity_factor']:.1f}%. PV mainly contributed during daytime high-value periods, improving renewable penetration and lowering marginal energy cost.", indent=6)
    add_report_line(pdf, font_name, f"- ESS: Average discharge {metrics['ess_avg_mw']:.1f} MW, total discharge {metrics['ess_energy_mwh']:.1f} MWh, and discharge-based capacity factor {metrics['ess_capacity_factor']:.1f}%. ESS was used selectively for peak shaving and energy arbitrage, indicating a control strategy focused on value capture rather than continuous cycling.", indent=6, gap_after=3)

    add_report_line(pdf, font_name, "5. TOU-Based Operation Strategy Analysis", bold=True, size=12)
    for item in metrics["tou_summary"]:
        add_report_line(pdf, font_name, f"- {item['label']}: SMR {item['smr_mw']:.1f} MW | GT {item['gt_mw']:.1f} MW | PV {item['pv_mw']:.1f} MW | ESS {item['ess_mw']:.1f} MW / {item['ess_soc_mwh']:.1f} MWh", indent=6)
    add_report_line(pdf, font_name, f"GT output increases from {offpeak_slot['gt_mw']:.1f} MW in Off-Peak to {peak_slot['gt_mw']:.1f} MW in On-Peak, a rise of {peak_slot['gt_mw'] - offpeak_slot['gt_mw']:.1f} MW. This variation confirms that GT is the primary balancing asset under TOU-based cost signals.", indent=4)
    add_report_line(pdf, font_name, f"During On-Peak periods, PV output rises to {peak_slot['pv_mw']:.1f} MW and ESS discharge reaches {peak_slot['ess_mw']:.1f} MW, producing a combined non-fossil / stored support effect of {peak_slot['pv_mw'] + peak_slot['ess_mw']:.1f} MW. This reduces reliance on higher-cost thermal or imported power at the most valuable time of day.", indent=4)
    add_report_line(pdf, font_name, "The TOU strategy minimizes cost by shifting storage contribution and renewable value toward expensive hours while maintaining SMR as a stable base layer and using GT only as the adjustable balancing margin.", indent=4, gap_after=3)

    add_report_line(pdf, font_name, "6. Overall Assessment and Recommendations", bold=True, size=12)
    add_report_line(pdf, font_name, f"Overall assessment: the optimization result is strong in operational stability, clear resource role allocation, and effective On-Peak support from PV and ESS. However, variable cost remains dominant at {metrics['variable_ratio']:.1f}% of total cost, which implies continued sensitivity to thermal dispatch and market price exposure.", indent=4)
    add_report_line(pdf, font_name, f"- Recommendation 1: expand or re-optimize ESS operation. Current average discharge of {metrics['ess_avg_mw']:.1f} MW suggests storage is valuable but selectively used; increasing usable power or duration could further reduce GT and grid exposure during On-Peak hours.", indent=6)
    add_report_line(pdf, font_name, "- Recommendation 2: reduce GT dependency through additional low-marginal-cost supply or tighter commitment logic. GT remains the main flexible asset, so even modest reductions in peak GT output would materially improve variable cost.", indent=6)
    add_report_line(pdf, font_name, "- Recommendation 3: improve PV utilization through curtailment minimization, demand alignment, or coordinated ESS charging. This would increase daytime renewable capture and raise the effective value of the existing solar asset.", indent=6)
    add_report_line(pdf, font_name, "- Recommendation 4: evaluate scenario-based TOU sensitivity. Testing alternative tariff conditions and fuel cost assumptions would improve confidence in operating policy and investment prioritization.", indent=6, gap_after=3)

    add_report_line(pdf, font_name, "7. Data Limitations and Assumptions", bold=True, size=12)
    add_report_line(pdf, font_name, "- The report assumes a 24-hour analysis horizon and interprets all average outputs over that period.", indent=6)
    add_report_line(pdf, font_name, "- Capacity factor values are calculated from average output or total discharge divided by rated capacity over 24 hours.", indent=6)
    add_report_line(pdf, font_name, "- Baseload generation cost is interpreted from the modeled low-variability generation block, while total cost and variable cost are taken directly from optimization output.", indent=6)
    add_report_line(pdf, font_name, "- External constraints such as maintenance schedules, reserve requirements, emissions limits, and forecast uncertainty are not explicitly represented in this narrative unless reflected in the optimization result.", indent=6)
    if explanation_lines:
        add_report_line(pdf, font_name, f"- Additional model note: {explanation_lines[0]}", indent=6)

# =========================================================
# 1. 결과 시각화 함수
# =========================================================
def plot_results(solution_data, params):
    if not solution_data: return

    T = params.time_steps
    times = range(T)
    
    if params.timestamps and len(params.timestamps) == T:
        time_labels = [t.split(" ")[-1] for t in params.timestamps]
    else:
        time_labels = [f"{int(t/4):02d}:{int(t%4)*15:02d}" for t in times]

    p_grid, p_pv = [], []
    gen_names = list(params.generators.keys())
    ess_names = list(params.ess.keys()) if params.ess else []
    
    gen_data = {g: [] for g in gen_names}
    ess_data = {e: [] for e in ess_names}

    for t in times:
        val = solution_data.get(t, {})
        p_grid.append(val.get('P_grid', 0))
        p_pv.append(val.get('P_PV', 0))
        for g in gen_names:
            gen_data[g].append(val.get(f'P_{g}', val.get(g, 0)))
        for e in ess_names:
            ess_data[e].append(val.get(f'P_dis_{e}', 0))

    # Merit Order: PV(0) -> SMR(1) -> GT(2) -> ESS(3) -> Grid(4)
    sources = []
    sources.append({"label": "PV", "data": p_pv, "total": sum(p_pv), "priority": 0, "color": "#2ca02c"})

    reds = ["#d62728", "#ff7f0e", "#e377c2", "#bcbd22", "#8c564b"]
    for i, g in enumerate(gen_names):
        name_upper = g.upper()
        if "SMR" in name_upper or "NUC" in name_upper:
            priority, color = 1, "#9467bd"
        else:
            priority, color = 2, reds[i % len(reds)]
        sources.append({"label": g, "data": gen_data[g], "total": sum(gen_data[g]), "priority": priority, "color": color})

    browns = ["#8B4513", "#A0522D", "#CD853F"]
    for i, e in enumerate(ess_names):
        sources.append({"label": f"{e} Dis", "data": ess_data[e], "total": sum(ess_data[e]), "priority": 3, "color": browns[i % len(browns)]})

    sources.append({"label": "Grid", "data": p_grid, "total": sum(p_grid), "priority": 4, "color": "#1f77b4"})
    sources.sort(key=lambda x: (x['priority'], -x['total']))

    y_arrays = [s['data'] for s in sources if s['total'] > 0.1]
    labels = [s['label'] for s in sources if s['total'] > 0.1]
    colors = [s['color'] for s in sources if s['total'] > 0.1]

    plt.figure(figsize=(12, 6))
    plt.stackplot(times, *y_arrays, labels=labels, colors=colors, alpha=0.9, edgecolor='white', linewidth=0.5)
    
    plt.title(f"Optimization Result (Cost Based)", fontsize=15, fontweight='bold')
    plt.ylabel("Power (MW)", fontsize=12)
    plt.xlabel("Time", fontsize=12)
    plt.xlim(0, T-1)
    
    ticks = range(0, T, 12)
    plt.xticks(ticks=ticks, labels=[time_labels[i] for i in ticks])
    
    handles, labels = plt.gca().get_legend_handles_labels()
    plt.legend(handles[::-1], labels[::-1], loc='upper left')
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.savefig("optimization_result.png")
    print(f"[Graph] Saved.")

# =========================================================
# 2. PDF 리포트 생성 (2단 레이아웃 + 소수점 포함)
# =========================================================
def create_pdf_report(explanation_text, solution_data=None, params=None, image_path="optimization_result.png", filename="Final_Report.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    
    font_path = r'C:\Windows\Fonts\malgun.ttf'
    font_name = 'Arial'
    if os.path.exists(font_path):
        try: 
            pdf.add_font('KoreanFont', '', fname=font_path)
            font_name = 'KoreanFont'
        except: 
            pass
    
    # Page 1
    pdf.add_page()
    pdf.set_font(font_name, '', 16)
    pdf.cell(0, 10, "<Energy Dispatch Report>", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(5)
    
    if os.path.exists(image_path): 
        pdf.image(image_path, x=15, w=180)
        pdf.ln(5)

    if solution_data and params:
        try:
            metrics = build_report_metrics(solution_data, params)
            if not render_llm_report(pdf, font_name, explanation_text):
                render_structured_report(pdf, font_name, metrics, explanation_text)
        except Exception as e:
            pdf.set_font(font_name, '', 10)
            fallback_text = normalize_explanation_text(explanation_text) if explanation_text else "No content."
            pdf.multi_cell(0, 6, fallback_text or "No content.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            print(f"[PDF] Structured report fallback: {e}")
    else:
        pdf.set_font(font_name, '', 10)
        fallback_text = normalize_explanation_text(explanation_text) if explanation_text else "No content."
        pdf.multi_cell(0, 6, fallback_text or "No content.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Page 2 (Table)
    if solution_data and params:
        pdf.add_page()
        pdf.set_font(font_name, '', 12)
        pdf.cell(0, 10, "Detailed Simulation Data (24h)", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.ln(2)
        
        gen_names = list(params.generators.keys())
        ess_names = list(params.ess.keys()) if params.ess else []
        headers = ["Time", "Grid", "PV"] + gen_names + [f"{e}" for e in ess_names] + ["Tot", "Dif"]
        
        page_width = 190
        col_gap = 4      
        block_width = (page_width - col_gap) / 2
        num_cols = len(headers)
        col_width = block_width / num_cols
        row_height = 4 
        
        total_steps = params.time_steps
        mid_point = (total_steps + 1) // 2
        
        def draw_table_block(start_idx, end_idx, x_start, y_start):
            # Header
            pdf.set_xy(x_start, y_start)
            pdf.set_font(font_name, '', 5)
            pdf.set_fill_color(220, 230, 255)
            for h in headers:
                pdf.cell(col_width, row_height, h, border=1, align='C', fill=True)
            
            current_y = y_start + row_height
            pdf.set_font(font_name, '', 4.5) 
            
            # Rows
            for t in range(start_idx, end_idx):
                if t >= total_steps: break
                pdf.set_xy(x_start, current_y)
                row = solution_data[t]
                
                vals = []
                t_label = params.timestamps[t].split(" ")[-1][:5] if params.timestamps else f"{t}"
                vals.append(t_label)
                vals.append(f"{row.get('P_grid',0):.1f}")
                vals.append(f"{row.get('P_PV',0):.1f}")
                
                p_gen_sum = 0
                for g in gen_names:
                    val = row.get(f'P_{g}', row.get(g, 0))
                    vals.append(f"{val:.1f}")
                    p_gen_sum += val
                
                p_ess_sum = 0
                for e in ess_names:
                    val = row.get(f'P_dis_{e}', 0)
                    vals.append(f"{val:.1f}")
                    p_ess_sum += val
                
                managed = row.get('P_grid',0) + p_gen_sum + p_ess_sum
                target = params.demand_profile[t]
                vals.append(f"{managed:.1f}")
                vals.append(f"{(managed-target):.1f}")
                
                for v in vals:
                    pdf.cell(col_width, row_height, v, border=1, align='C')
                current_y += row_height

        start_y = pdf.get_y()
        draw_table_block(0, mid_point, 10, start_y)
        draw_table_block(mid_point, total_steps, 10 + block_width + col_gap, start_y)

    pdf.output(filename)
    print(f"[PDF] Saved to {filename}")

# =========================================================
# 3. 메인 실행
# =========================================================
if __name__ == "__main__":
    graph = build_graph()
    
    # CSV 읽어서 프롬프트 생성
    gt_min, gt_max = 40.0, 120.0
    csv_file = "gtfuel.csv"
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            target_col = next((c for c in df.columns if "power" in c and "mw" in c), None)
            if target_col:
                gt_min = float(df[target_col].min())
                gt_max = float(df[target_col].max())
                print(f">> Fuel CSV Loaded. GT Range: {gt_min:.1f}~{gt_max:.1f} MW")
        except: pass

    user_request = f"""
    가스터빈(GT) 2대: 비용은 파일참고(비쌈), 범위 {gt_min}~{gt_max}MW.
    SMR 1대: 비용 아주 쌈, 91~121MW.
    ESS 1대: 300MWh, 80MW.
    """
    
    initial_state = {"problem_text": user_request, "solution_output": None, "explanation": None}
    
    print(">> Running Workflow...")
    try:
        result = graph.invoke(initial_state)
        sol = result.get("solution_output")
        final_params = result.get("params") 
        
        if sol and final_params:
            plot_results(sol, final_params)
            create_pdf_report(result.get("explanation"), solution_data=sol, params=final_params)
            print(f">> Success! Total Cost: {sol.get('Total_Cost', 0):,.0f} KRW")
        else:
            print(">> No solution.")
            
    except Exception as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()
