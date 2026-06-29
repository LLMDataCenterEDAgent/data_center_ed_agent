import os
import re
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib-cache")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


# ─────────────────────────────────────────
#  Data helpers
# ─────────────────────────────────────────

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

    interval_hours = float(getattr(params, "interval_hours", 0.25) or 0.25)
    gen_cols = [key for key in rows[0] if key.endswith("_mw") and key.startswith(("GT", "SMR"))]
    total_grid = sum(row["grid_mw"] for row in rows) * interval_hours
    total_pv = sum(row["pv_mw"] for row in rows) * interval_hours
    total_ess_dis = sum(row["ess_discharge_mw"] for row in rows) * interval_hours
    total_ess_chg = sum(row["ess_charge_mw"] for row in rows) * interval_hours
    total_gen = sum(sum(row.get(col, 0.0) for col in gen_cols) for row in rows) * interval_hours
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


# ─────────────────────────────────────────
#  Chart
# ─────────────────────────────────────────

def plot_results(solution_data, params, output_path):
    if not solution_data or not params:
        return None

    output_path = Path(output_path)
    T = params.time_steps
    times = range(T)
    if params.timestamps and len(params.timestamps) == T:
        time_labels = [str(t).split(" ")[-1] for t in params.timestamps]
    else:
        interval_minutes = int(getattr(params, "interval_minutes", 15) or 15)
        time_labels = [
            f"{int((t * interval_minutes) / 60) % 24:02d}:{int((t * interval_minutes) % 60):02d}"
            for t in times
        ]

    p_grid, p_pv, p_ess_dis = [], [], []
    gen_data = {g: [] for g in params.generators}

    for t in times:
        val = solution_data.get(t, {})
        p_grid.append(val.get("P_grid", 0.0))
        p_pv.append(val.get("P_PV", 0.0))
        p_ess_dis.append(val.get("P_dis_ESS1", val.get("P_discharge", 0.0)))
        for gen_name in params.generators:
            gen_data[gen_name].append(val.get(f"P_{gen_name}", val.get(gen_name, 0.0)))

    color_map = {
        "SMR1": "#4C5FD5", "PV": "#35A853",
        "GT1": "#E85D3F", "GT2": "#F4A62A",
        "ESS Dis": "#9B6A3B", "Grid": "#2D8ACF",
    }
    sources = []
    if "SMR1" in gen_data:
        sources.append({"label": "SMR1", "data": gen_data.pop("SMR1"), "color": color_map["SMR1"]})
    sources.append({"label": "PV", "data": p_pv, "color": color_map["PV"]})
    for gen_name in ["GT1", "GT2"]:
        if gen_name in gen_data:
            sources.append({"label": gen_name, "data": gen_data.pop(gen_name), "color": color_map[gen_name]})
    extra = [
        {"label": "Grid", "data": p_grid, "color": color_map["Grid"]},
        {"label": "ESS Dis", "data": p_ess_dis, "color": color_map["ESS Dis"]},
    ]
    for gen_name, values in gen_data.items():
        extra.append({"label": gen_name, "data": values, "color": "#495057"})
    extra.sort(key=lambda s: sum(s["data"]), reverse=True)
    sources.extend(extra)

    total_supply = [sum(s["data"][i] for s in sources) for i in range(T)]
    net_load = list(params.demand_profile or [0] * T)
    peak_idx = total_supply.index(max(total_supply)) if total_supply else 0

    fig, ax = plt.subplots(figsize=(13.5, 6.8), facecolor="#F7F8FB")
    ax.set_facecolor("#FFFFFF")
    ax.stackplot(times, *[s["data"] for s in sources],
                 labels=[s["label"] for s in sources],
                 colors=[s["color"] for s in sources],
                 alpha=0.92, linewidth=0.35, edgecolor="#FFFFFF")
    ax.plot(times, net_load, color="#1F2937", linewidth=2.0, label="Net Load", alpha=0.92)
    ax.plot(times, total_supply, color="#111827", linewidth=1.15, linestyle="--", label="Total Supply", alpha=0.65)

    if total_supply:
        ax.scatter([peak_idx], [total_supply[peak_idx]], color="#111827", s=42, zorder=5)
        ax.annotate(
            f"Peak {total_supply[peak_idx]:,.1f} MW",
            xy=(peak_idx, total_supply[peak_idx]), xytext=(10, 18),
            textcoords="offset points", fontsize=9, color="#1F2937",
            bbox={"boxstyle": "round,pad=0.35", "fc": "#FFFFFF", "ec": "#D6DAE5", "alpha": 0.96},
            arrowprops={"arrowstyle": "->", "color": "#6B7280", "lw": 0.8},
        )

    ax.set_title("Optimized Energy Dispatch Mix", fontsize=16, fontweight="bold", loc="left", pad=16, color="#1F2937")
    ax.text(0, 1.015, "Stacked generation schedule with net-load and total-supply overlays",
            transform=ax.transAxes, fontsize=9.5, color="#667085")
    ax.set_ylabel("Power (MW)", fontsize=10, color="#4B5563")
    ax.set_xlabel("Dispatch interval", fontsize=10, color="#4B5563")
    tick_step = max(1, int(T / 8))
    ticks = range(0, T, tick_step)
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([time_labels[i] for i in ticks], rotation=0, fontsize=9)
    ax.set_xlim(0, max(T - 1, 1))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.tick_params(axis="y", labelsize=9, colors="#4B5563")
    ax.tick_params(axis="x", colors="#4B5563")
    ax.grid(True, axis="y", linestyle="-", color="#E6E8EF", linewidth=0.8)
    ax.grid(False, axis="x")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#D6DAE5")
    ax.spines["bottom"].set_color("#D6DAE5")

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="upper center",
              bbox_to_anchor=(0.5, -0.12), ncol=min(4, max(1, len(labels))),
              frameon=False, fontsize=9)
    fig.tight_layout(rect=[0.02, 0.06, 0.98, 0.96])
    fig.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    return str(output_path)


# ─────────────────────────────────────────
#  PDF — color palette
# ─────────────────────────────────────────

_C_NAVY      = (15, 23, 42)
_C_BLUE      = (37, 99, 235)
_C_WHITE     = (255, 255, 255)
_C_SUBTITLE  = (147, 197, 253)
_C_BODY      = (31, 41, 55)
_C_SUBTEXT   = (100, 116, 139)
_C_CARD_BG   = (248, 250, 252)
_C_DIVIDER   = (226, 232, 240)
_C_PAGE_BG   = (240, 242, 246)

_KPI_CARDS = [
    ("Total Cost",        "KRW",  (37,  99,  235)),
    ("PV Renewable Share","%",    (16,  185, 129)),
    ("Grid Import",       "MWh",  (139, 92,  246)),
    ("Generator Output",  "MWh",  (245, 158, 11)),
    ("Peak Demand",       "MW",   (239, 68,  68)),
]

_SECTION_META = [
    (r"executive summary",               (59,  130, 246), "EXECUTIVE SUMMARY"),
    (r"system configuration",            (139, 92,  246), "SYSTEM CONFIGURATION"),
    (r"cost structure",                  (16,  185, 129), "COST STRUCTURE"),
    (r"dispatch strategy",               (245, 158, 11),  "DISPATCH STRATEGY"),
    (r"tou.based operation|time.of.use", (6,   182, 212), "TOU OPERATION STRATEGY"),
    (r"assessment.*recommendation|recommendation", (239, 68, 68),   "RECOMMENDATIONS"),
    (r"data limitation|limitation|assumption",     (156, 163, 175), "LIMITATIONS & ASSUMPTIONS"),
]


def _classify(title: str):
    t = title.lower()
    for pattern, color, label in _SECTION_META:
        if re.search(pattern, t):
            return color, label
    return (59, 130, 246), title.upper()


# ─────────────────────────────────────────
#  PDF — drawing helpers
# ─────────────────────────────────────────

def _font(pdf, font_name, style, size):
    try:
        pdf.set_font(font_name, style, size)
    except Exception:
        pdf.set_font(font_name, "", size)


def _load_fonts(pdf):
    candidates = [Path("NanumGothic-Regular.ttf"), Path("/Library/Fonts/AppleGothic.ttf")]
    bold_cands  = [Path("NanumGothic-Bold.ttf")]
    for fp in candidates:
        if fp.exists():
            try:
                pdf.add_font("KF", "", fname=str(fp), uni=True)
                for bp in bold_cands:
                    if bp.exists():
                        pdf.add_font("KF", "B", fname=str(bp), uni=True)
                        break
                return "KF"
            except Exception:
                continue
    return "Helvetica"


def _draw_header(pdf, font_name):
    """Dark navy header banner with blue left accent."""
    x, w, h = pdf.l_margin, pdf.w - pdf.l_margin - pdf.r_margin, 28

    # Background
    pdf.set_fill_color(*_C_NAVY)
    pdf.rect(x, 10, w, h, "F")

    # Left accent bar
    pdf.set_fill_color(*_C_BLUE)
    pdf.rect(x, 10, 5, h, "F")

    # Title
    pdf.set_xy(x + 8, 14)
    pdf.set_text_color(*_C_WHITE)
    _font(pdf, font_name, "B", 15)
    pdf.cell(0, 7, "Data Center Energy Dispatch Report", ln=False)

    # Subtitle
    pdf.set_xy(x + 8, 22)
    pdf.set_text_color(*_C_SUBTITLE)
    _font(pdf, font_name, "", 8.5)
    pdf.cell(0, 5, "Scenario-based optimization  |  PV · GT · SMR · ESS microgrid", ln=False)

    # Date (right-aligned)
    from datetime import date
    pdf.set_xy(x, 33)
    pdf.set_text_color(*_C_SUBTITLE)
    _font(pdf, font_name, "", 7.5)
    pdf.cell(w, 4, date.today().strftime("%Y-%m-%d"), align="R", ln=False)

    pdf.ln(0)
    pdf.set_y(10 + h + 5)


def _draw_kpi_row(pdf, font_name, metrics):
    """Five KPI cards in a single row."""
    from fpdf import XPos, YPos

    x0  = pdf.l_margin
    w   = pdf.w - pdf.l_margin - pdf.r_margin
    gap = 2.5
    card_w = (w - gap * 4) / 5
    card_h = 22
    y0 = pdf.get_y()

    kpi_values = [
        f"{metrics.get('total_cost', 0):,.0f}",
        f"{metrics.get('pv_share', 0):.1f}",
        f"{metrics.get('total_grid', 0):,.1f}",
        f"{metrics.get('total_generation', 0):,.1f}",
        f"{metrics.get('peak_supply', 0):,.1f}",
    ]

    for i, ((label, unit, accent), value) in enumerate(zip(_KPI_CARDS, kpi_values)):
        cx = x0 + i * (card_w + gap)

        # Card background
        pdf.set_fill_color(*_C_CARD_BG)
        pdf.rect(cx, y0, card_w, card_h, "F")

        # Colored top bar
        pdf.set_fill_color(*accent)
        pdf.rect(cx, y0, card_w, 3, "F")

        # Label
        pdf.set_xy(cx + 2, y0 + 4.5)
        pdf.set_text_color(*_C_SUBTEXT)
        _font(pdf, font_name, "", 6)
        pdf.cell(card_w - 4, 3.5, label.upper(), new_x=XPos.LEFT, new_y=YPos.NEXT)

        # Value
        pdf.set_xy(cx + 2, y0 + 9)
        pdf.set_text_color(*_C_BODY)
        _font(pdf, font_name, "B", 11)
        pdf.cell(card_w - 4, 6, value, new_x=XPos.LEFT, new_y=YPos.NEXT)

        # Unit
        pdf.set_xy(cx + 2, y0 + 16)
        pdf.set_text_color(*_C_SUBTEXT)
        _font(pdf, font_name, "", 6.5)
        pdf.cell(card_w - 4, 3.5, unit, new_x=XPos.LEFT, new_y=YPos.NEXT)

    pdf.set_y(y0 + card_h + 5)


def _draw_section_label(pdf, font_name, text):
    """Small uppercase section label with a blue left accent."""
    x, w = pdf.l_margin, pdf.w - pdf.l_margin - pdf.r_margin
    y = pdf.get_y()

    pdf.set_fill_color(*_C_BLUE)
    pdf.rect(x, y, 3.5, 7, "F")

    pdf.set_fill_color(235, 242, 255)
    pdf.rect(x + 3.5, y, w - 3.5, 7, "F")

    pdf.set_xy(x + 6, y + 1)
    pdf.set_text_color(*_C_BLUE)
    _font(pdf, font_name, "B", 8)
    pdf.cell(0, 5, text)
    pdf.ln(9)


def _draw_report_sections(pdf, font_name, text):
    """Parse markdown into sections and draw each with a colored left bar."""
    from fpdf import XPos, YPos

    raw_sections = re.split(r'\n(?=#{1,3}\s)', text.strip())

    for chunk in raw_sections:
        chunk = chunk.strip()
        if not chunk:
            continue

        m = re.match(r'^#{1,3}\s+(.*)', chunk)
        if m:
            title    = m.group(1).strip()
            body_raw = chunk[m.end():].strip()
        else:
            title    = "Summary"
            body_raw = chunk

        color, display_title = _classify(title)

        # Keep section on page if possible (rough estimate: need at least 20mm)
        if pdf.get_y() > pdf.h - pdf.b_margin - 20:
            pdf.add_page()

        _draw_section_heading(pdf, font_name, display_title, color)
        _draw_section_body(pdf, font_name, body_raw)
        pdf.ln(3)


def _draw_section_heading(pdf, font_name, title, color):
    from fpdf import XPos, YPos

    x, w = pdf.l_margin, pdf.w - pdf.l_margin - pdf.r_margin
    y, h = pdf.get_y(), 8

    r, g, b = color
    # Tinted background (mix color with white at 90%)
    tr = min(int(r * 0.1 + 255 * 0.9), 255)
    tg = min(int(g * 0.1 + 255 * 0.9), 255)
    tb = min(int(b * 0.1 + 255 * 0.9), 255)

    pdf.set_fill_color(tr, tg, tb)
    pdf.rect(x, y, w, h, "F")

    pdf.set_fill_color(*color)
    pdf.rect(x, y, 4, h, "F")

    pdf.set_xy(x + 6.5, y + 1.8)
    pdf.set_text_color(*color)
    _font(pdf, font_name, "B", 8)
    pdf.cell(w - 7, 4.5, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1.5)


def _draw_section_body(pdf, font_name, text):
    from fpdf import XPos, YPos

    x = pdf.l_margin + 5
    w = pdf.w - pdf.l_margin - pdf.r_margin - 5
    lh = 5.2

    pdf.set_text_color(*_C_BODY)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            pdf.ln(1.5)
            continue

        line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
        line = re.sub(r'`(.*?)`', r'\1', line)

        is_bullet = line.startswith("- ") or line.startswith("* ")
        if is_bullet:
            line = "•  " + line[2:].strip()
            _font(pdf, font_name, "", 8.8)
            pdf.set_x(x + 3)
            pdf.multi_cell(w - 3, lh, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            _font(pdf, font_name, "", 8.8)
            pdf.set_x(x)
            pdf.multi_cell(w, lh, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _draw_divider(pdf):
    x, w = pdf.l_margin, pdf.w - pdf.l_margin - pdf.r_margin
    y = pdf.get_y()
    pdf.set_draw_color(*_C_DIVIDER)
    pdf.line(x, y, x + w, y)
    pdf.ln(3)


# ─────────────────────────────────────────
#  PDF — public entry point
# ─────────────────────────────────────────

def create_pdf_report(explanation_text, image_path, output_path, metrics=None):
    from fpdf import FPDF

    output_path = Path(output_path)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(left=12, top=10, right=12)
    pdf.add_page()

    font_name = _load_fonts(pdf)

    # ── Header banner
    _draw_header(pdf, font_name)

    # ── KPI cards
    if metrics:
        _draw_kpi_row(pdf, font_name, metrics)
        _draw_divider(pdf)

    # ── Dispatch chart
    if image_path and os.path.exists(image_path):
        _draw_section_label(pdf, font_name, "ENERGY DISPATCH MIX")
        pdf.image(image_path, x=pdf.l_margin, w=pdf.w - pdf.l_margin - pdf.r_margin)
        pdf.ln(4)

    # ── AI Report sections
    if explanation_text:
        _draw_divider(pdf)
        _draw_section_label(pdf, font_name, "AI ANALYSIS REPORT")
        safe = explanation_text
        if font_name == "Helvetica":
            safe = safe.encode("latin-1", "replace").decode("latin-1")
        _draw_report_sections(pdf, font_name, safe)

    pdf.output(str(output_path))
    return str(output_path)
