import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib-cache")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def solution_rows(solution_data, params):
    rows = []
    if not solution_data or not params:
        return rows

    gen_names = list(params.generators.keys())
    for t in range(params.time_steps):
        row_data = solution_data.get(t, {})
        row = {
            "time": params.timestamps[t] if params.timestamps else str(t),
            "grid_mw": row_data.get("P_grid", 0.0),
            "pv_mw": row_data.get("P_PV", 0.0),
            "ess_discharge_mw": row_data.get("P_dis_ESS1", row_data.get("P_discharge", 0.0)),
            "ess_charge_mw": row_data.get("P_chg_ESS1", row_data.get("P_charge", 0.0)),
            "net_load_mw": params.demand_profile[t] if params.demand_profile else 0.0,
        }
        generator_total = 0.0
        for gen_name in gen_names:
            value = row_data.get(f"P_{gen_name}", row_data.get(gen_name, 0.0))
            row[f"{gen_name}_mw"] = value
            generator_total += value
        row["managed_supply_mw"] = row["grid_mw"] + generator_total + row["ess_discharge_mw"]
        row["balance_diff_mw"] = row["managed_supply_mw"] - row["net_load_mw"]
        rows.append(row)
    return rows


def summary_metrics(solution_data, params):
    rows = solution_rows(solution_data, params)
    if not rows:
        return {}

    gen_cols = [key for key in rows[0] if key.endswith("_mw") and key.startswith(("GT", "SMR"))]
    total_grid = sum(row["grid_mw"] for row in rows)
    total_pv = sum(row["pv_mw"] for row in rows)
    total_ess_dis = sum(row["ess_discharge_mw"] for row in rows)
    total_ess_chg = sum(row["ess_charge_mw"] for row in rows)
    total_gen = sum(sum(row.get(col, 0.0) for col in gen_cols) for row in rows)
    total_supply = total_grid + total_pv + total_gen + total_ess_dis
    peak_row = max(rows, key=lambda row: row["managed_supply_mw"] + row["pv_mw"])
    return {
        "total_cost": solution_data.get("Total_Cost", 0.0),
        "total_supply": total_supply,
        "total_grid": total_grid,
        "total_pv": total_pv,
        "pv_share": (total_pv / total_supply * 100.0) if total_supply else 0.0,
        "total_generation": total_gen,
        "total_ess_discharge": total_ess_dis,
        "total_ess_charge": total_ess_chg,
        "peak_time": peak_row["time"],
        "peak_supply": peak_row["managed_supply_mw"] + peak_row["pv_mw"],
    }


def plot_results(solution_data, params, output_path):
    if not solution_data or not params:
        return None

    output_path = Path(output_path)
    T = params.time_steps
    times = range(T)
    if params.timestamps and len(params.timestamps) == T:
        time_labels = [str(t).split(" ")[-1] for t in params.timestamps]
    else:
        time_labels = [f"{int(t / 4):02d}:{int(t % 4) * 15:02d}" for t in times]

    p_grid = []
    p_pv = []
    p_ess_dis = []
    gen_data = {g: [] for g in params.generators}

    for t in times:
        val = solution_data.get(t, {})
        p_grid.append(val.get("P_grid", 0.0))
        p_pv.append(val.get("P_PV", 0.0))
        p_ess_dis.append(val.get("P_dis_ESS1", val.get("P_discharge", 0.0)))
        for gen_name in params.generators:
            gen_data[gen_name].append(val.get(f"P_{gen_name}", val.get(gen_name, 0.0)))

    color_map = {
        "SMR1": "#6f5aa7",
        "PV": "#2f9e44",
        "GT1": "#c92a2a",
        "GT2": "#f08c00",
        "ESS Dis": "#7c4d3a",
        "Grid": "#1971c2",
    }
    sources = []
    if "SMR1" in gen_data:
        sources.append({"label": "SMR1", "data": gen_data.pop("SMR1"), "color": color_map["SMR1"]})
    sources.append({"label": "PV", "data": p_pv, "color": color_map["PV"]})
    for gen_name in ["GT1", "GT2"]:
        if gen_name in gen_data:
            sources.append({"label": gen_name, "data": gen_data.pop(gen_name), "color": color_map[gen_name]})
    extra_sources = [
        {"label": "Grid", "data": p_grid, "color": color_map["Grid"]},
        {"label": "ESS Dis", "data": p_ess_dis, "color": color_map["ESS Dis"]},
    ]
    for gen_name, values in gen_data.items():
        extra_sources.append({"label": gen_name, "data": values, "color": "#495057"})
    extra_sources.sort(key=lambda item: sum(item["data"]), reverse=True)
    sources.extend(extra_sources)

    plt.figure(figsize=(12, 6))
    plt.stackplot(
        times,
        *[source["data"] for source in sources],
        labels=[source["label"] for source in sources],
        colors=[source["color"] for source in sources],
        alpha=0.88,
    )
    plt.title("Optimization Result: Energy Mix", fontsize=15, fontweight="bold")
    plt.ylabel("Power (MW)")
    plt.xlabel("Time")
    tick_step = max(1, int(T / 8))
    ticks = range(0, T, tick_step)
    plt.xticks(ticks=ticks, labels=[time_labels[i] for i in ticks], rotation=0)
    plt.xlim(0, max(T - 1, 1))
    handles, labels = plt.gca().get_legend_handles_labels()
    plt.legend(handles[::-1], labels[::-1], loc="upper left", title="Source")
    plt.grid(True, linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()
    return str(output_path)


def create_pdf_report(explanation_text, image_path, output_path):
    from fpdf import FPDF, XPos, YPos

    output_path = Path(output_path)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    font_candidates = [Path("NanumGothic-Regular.ttf"), Path("/Library/Fonts/AppleGothic.ttf")]
    bold_candidates = [Path("NanumGothic-Bold.ttf")]
    font_name = "Arial"
    for font_path in font_candidates:
        if font_path.exists():
            try:
                pdf.add_font("KoreanFont", "", fname=str(font_path), uni=True)
                for bold_path in bold_candidates:
                    if bold_path.exists():
                        pdf.add_font("KoreanFont", "B", fname=str(bold_path), uni=True)
                        break
                font_name = "KoreanFont"
                break
            except Exception:
                continue

    pdf.set_font(font_name, "B" if font_name == "KoreanFont" else "", 14)
    pdf.cell(0, 10, "AI Data Center Energy Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(5)
    if image_path and os.path.exists(image_path):
        pdf.image(image_path, x=15, w=180)
        pdf.ln(5)

    safe_text = _clean_markdown_text(explanation_text or "No report content.")
    if font_name == "Arial":
        safe_text = safe_text.encode("latin-1", "replace").decode("latin-1")
    _write_markdown_like_pdf(pdf, safe_text, font_name)
    pdf.output(str(output_path))
    return str(output_path)


def _clean_markdown_text(text):
    replacements = {
        "**": "",
        "__": "",
        "`": "",
        "<Energy Dispatch Report>": "Energy Dispatch Report",
    }
    cleaned = text
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return cleaned


def _write_markdown_like_pdf(pdf, text, font_name):
    from fpdf import XPos, YPos

    bullet_indent = 7
    line_height = 5.4

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            pdf.ln(2)
            continue

        heading_level = 0
        while line.startswith("#"):
            heading_level += 1
            line = line[1:].strip()

        is_bullet = line.startswith("- ")
        if is_bullet:
            line = line[2:].strip()

        if heading_level:
            size = 12 if heading_level <= 2 else 10.5
            pdf.ln(2)
            _set_pdf_font(pdf, font_name, "B", size)
            pdf.multi_cell(0, 6.2, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
        elif is_bullet:
            _set_pdf_font(pdf, font_name, "", 9.2)
            x = pdf.get_x()
            pdf.set_x(x + bullet_indent)
            pdf.multi_cell(0, line_height, f"- {line}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            _set_pdf_font(pdf, font_name, "", 9.4)
            pdf.multi_cell(0, line_height, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _set_pdf_font(pdf, font_name, style, size):
    try:
        pdf.set_font(font_name, style, size)
    except RuntimeError:
        pdf.set_font(font_name, "", size)
