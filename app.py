import tempfile
import os
import re
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from openai import OpenAI

from services.supabase_store import SupabaseStore
from ui.reporting import create_pdf_report, plot_results, solution_rows, summary_metrics
from workflow.graph import build_graph


st.set_page_config(page_title="Data Center ED Agent", page_icon="⚡", layout="wide")


# ─────────────────────────────────────────
#  CSS — only custom HTML components touched
#  Native Streamlit inputs/labels left alone
# ─────────────────────────────────────────

def inject_css(dark: bool):
    if dark:
        page_bg    = "#0e1117"
        card_bg    = "#1e2130"
        text       = "#f1f5f9"
        subtext    = "#94a3b8"
        input_bg   = "#111827"
        input_text = "#f8fafc"
        input_bd   = "rgba(148,163,184,0.45)"
        shadow     = "rgba(0,0,0,0.3)"
        h2_color   = "#60a5fa"
        h2_border  = "rgba(96,165,250,0.2)"
        tou_border = "rgba(255,255,255,0.07)"
        tou_even   = "rgba(255,255,255,0.03)"
    else:
        page_bg    = "#f0f2f6"
        card_bg    = "#ffffff"
        text       = "#1f2937"
        subtext    = "#6b7280"
        input_bg   = "#ffffff"
        input_text = "#111827"
        input_bd   = "#cbd5e1"
        shadow     = "rgba(0,0,0,0.08)"
        h2_color   = "#1e3a8a"
        h2_border  = "#eff6ff"
        tou_border = "rgba(0,0,0,0.08)"
        tou_even   = "#f8faff"

    dark_css = ""
    if dark:
        dark_css = f"""
        /* Dark mode: force Streamlit native text to light */
        label, label p, label span,
        div[data-testid="stWidgetLabel"] p,
        div[data-testid="stWidgetLabel"] span,
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stMarkdownContainer"] li,
        div[data-testid="stMarkdownContainer"] span,
        div[data-testid="stText"] p,
        div[data-testid="stCaption"] p,
        div[data-testid="stExpander"] summary p,
        div[data-testid="stExpander"] summary span,
        div[data-testid="stTabs"] button[role="tab"],
        div[data-testid="stTabs"] button p,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]) {{
            color: {text} !important;
        }}
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]),
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):hover,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):focus,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):active,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]) p,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):hover p,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):focus p,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):active p,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]) span,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):hover span,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):focus span,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):active span {{
            color: #111827 !important;
        }}
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]) {{
            background-color: #ffffff !important;
            border-color: #cbd5e1 !important;
        }}
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):hover,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):focus,
        div[data-testid="stButton"]:not([data-testid="stDownloadButton"]) button:not([kind="primary"]):active {{
            background-color: #f8fafc !important;
            border-color: #94a3b8 !important;
            box-shadow: none !important;
        }}
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div {{
            color: {text} !important;
        }}
        """

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

        /* Page background only — native Streamlit components untouched */
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stHeader"] {{
            background: {page_bg} !important;
        }}

        /* ── Dashboard header (always dark gradient) ── */
        .db-header {{
            background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 60%, #2563eb 100%);
            border-radius: 16px;
            padding: 2rem 2.5rem;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .db-header h1 {{ color: #fff !important; font-size: 1.75rem; font-weight: 700; margin: 0; line-height: 1.2; }}
        .db-header p  {{ color: #93c5fd !important; font-size: .875rem; margin: .35rem 0 0; }}
        .db-header div {{ color: #93c5fd; font-size: .75rem; line-height: 1.8; }}
        .db-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 20px; padding: .3rem .9rem;
            color: #bfdbfe !important; font-size: .78rem; font-weight: 500;
            margin: .25rem .2rem 0;
        }}
        .db-badge.ok   {{ background: rgba(16,185,129,.2); border-color: rgba(16,185,129,.4); color: #6ee7b7 !important; }}
        .db-badge.warn {{ background: rgba(245,158,11,.2);  border-color: rgba(245,158,11,.4);  color: #fcd34d !important; }}

        /* ── KPI cards ── */
        .kpi-card {{
            flex: 1; min-width: 140px;
            background: {card_bg};
            border-radius: 14px;
            padding: 1.15rem 1.35rem;
            box-shadow: 0 2px 8px {shadow};
            border-top: 4px solid var(--accent);
            position: relative; overflow: hidden;
        }}
        .kpi-card::after {{
            content: ''; position: absolute; right: -14px; top: -14px;
            width: 72px; height: 72px; border-radius: 50%;
            background: var(--accent); opacity: .08;
        }}
        .kpi-label {{ font-size: .72rem; font-weight: 600; color: {subtext}; text-transform: uppercase; letter-spacing: .05em; margin-bottom: .35rem; }}
        .kpi-value {{ font-size: 1.65rem; font-weight: 700; color: {text}; line-height: 1; }}
        .kpi-unit  {{ font-size: .75rem; font-weight: 500; color: {subtext}; margin-left: .25rem; }}
        .kpi-sub   {{ font-size: .75rem; color: {subtext}; margin-top: .3rem; }}

        /* ── Section card ── */
        .section-card {{
            background: {card_bg};
            border-radius: 14px;
            padding: 1.5rem 1.75rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 1px 6px {shadow};
        }}
        .section-card h2 {{
            font-size: 1rem; font-weight: 700; color: {h2_color};
            margin: 0 0 1rem; padding-bottom: .6rem;
            border-bottom: 2px solid {h2_border};
            display: flex; align-items: center; gap: .5rem;
        }}

        /* ── Report blocks ── */
        .report-block {{
            border-left: 4px solid #3b82f6;
            border-radius: 0 10px 10px 0;
            padding: 1rem 1.2rem;
            margin-bottom: 1rem;
        }}
        .report-block h3 {{ font-size: .85rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; margin: 0 0 .5rem; }}
        .report-block p  {{ font-size: .875rem; color: {text}; line-height: 1.65; margin: 0; }}
        .report-block ul {{ font-size: .875rem; color: {text}; padding-left: 1.2rem; margin: 0; line-height: 1.7; }}

        .report-block.exec     {{ border-color: #3b82f6; background: rgba(59,130,246,.08); }}
        .report-block.exec h3  {{ color: #60a5fa; }}
        .report-block.config   {{ border-color: #8b5cf6; background: rgba(139,92,246,.08); }}
        .report-block.config h3{{ color: #a78bfa; }}
        .report-block.cost     {{ border-color: #10b981; background: rgba(16,185,129,.08); }}
        .report-block.cost h3  {{ color: #34d399; }}
        .report-block.dispatch {{ border-color: #f59e0b; background: rgba(245,158,11,.08); }}
        .report-block.dispatch h3 {{ color: #fbbf24; }}
        .report-block.tou      {{ border-color: #06b6d4; background: rgba(6,182,212,.08); }}
        .report-block.tou h3   {{ color: #22d3ee; }}
        .report-block.rec      {{ border-color: #ef4444; background: rgba(239,68,68,.08); }}
        .report-block.rec h3   {{ color: #f87171; }}
        .report-block.limit    {{ border-color: #9ca3af; background: rgba(156,163,175,.08); }}
        .report-block.limit h3 {{ color: #9ca3af; }}

        /* ── TOU table ── */
        .tou-table {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
        .tou-table th {{ background: #1e3a8a; color: #fff; font-weight: 600; padding: .55rem .75rem; text-align: center; }}
        .tou-table td {{ padding: .5rem .75rem; text-align: center; color: {text}; border-bottom: 1px solid {tou_border}; }}
        .tou-table tr:nth-child(even) td {{ background: {tou_even}; }}
        .badge-off {{ background: rgba(59,130,246,.15);  color: #60a5fa; border-radius: 20px; padding: 2px 10px; font-weight: 600; font-size: .75rem; }}
        .badge-mid {{ background: rgba(245,158,11,.15);  color: #fbbf24; border-radius: 20px; padding: 2px 10px; font-weight: 600; font-size: .75rem; }}
        .badge-on  {{ background: rgba(236,72,153,.15);  color: #f472b6; border-radius: 20px; padding: 2px 10px; font-weight: 600; font-size: .75rem; }}

        /* ── Native input contrast and borders ── */
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextArea"] textarea {{
            background-color: {input_bg} !important;
            color: {input_text} !important;
            border: 0 !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            outline: none !important;
        }}
        div[data-baseweb="input"],
        div[data-baseweb="textarea"] {{
            background-color: {input_bg} !important;
            border: 1px solid {input_bd} !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            outline: none !important;
        }}
        div[data-testid="stTextInput"] div[data-baseweb="base-input"],
        div[data-testid="stNumberInput"] div[data-baseweb="base-input"],
        div[data-testid="stTextArea"] div[data-baseweb="base-input"],
        div[data-testid="stTextInput"] div[data-baseweb="input"] > div,
        div[data-testid="stNumberInput"] div[data-baseweb="input"] > div,
        div[data-testid="stTextArea"] div[data-baseweb="textarea"] > div {{
            background-color: {input_bg} !important;
            border-color: {input_bd} !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }}
        div[data-testid="stNumberInputContainer"] {{
            background-color: {input_bg} !important;
            border: 1px solid {input_bd} !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            overflow: hidden !important;
        }}
        div[data-testid="stNumberInputContainer"] div[data-baseweb="input"] {{
            border: 0 !important;
            border-radius: 10px 0 0 10px !important;
        }}
        div[data-testid="stNumberInputContainer"] div[data-baseweb="input"]:focus-within {{
            border: 0 !important;
        }}
        div[data-baseweb="input"] input,
        div[data-baseweb="textarea"] textarea {{
            background-color: {input_bg} !important;
            color: {input_text} !important;
            -webkit-text-fill-color: {input_text} !important;
        }}
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stNumberInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus {{
            box-shadow: none !important;
            outline: none !important;
        }}
        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="textarea"]:focus-within {{
            border-color: #94a3b8 !important;
            box-shadow: none !important;
            outline: none !important;
        }}
        div[data-testid="stNumberInput"] button {{
            background-color: {input_bg} !important;
            color: {input_text} !important;
            border: 0 !important;
            box-shadow: none !important;
            border-radius: 0 !important;
        }}
        div[data-testid="stNumberInputContainer"] button:hover,
        div[data-testid="stNumberInputContainer"] button:focus {{
            background-color: {input_bg} !important;
            border: 0 !important;
            box-shadow: none !important;
            outline: none !important;
        }}
        div[data-testid="stNumberInput"] svg {{
            fill: {input_text} !important;
        }}

        /* ── Minor Streamlit tweaks ── */
        div[data-testid="stTabs"] button[role="tab"] {{ font-weight: 600; font-size: .875rem; }}
        div[data-testid="stButton"] button {{ border-radius: 10px; font-weight: 600; }}
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stDownloadButton"] button {{ color: #ffffff !important; }}
        div[data-testid="stDataFrame"] {{ border-radius: 10px; overflow: hidden; }}

        {dark_css}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────
#  Header
# ─────────────────────────────────────────

def render_page_header(store_mode):
    supabase_ok = store_mode == "supabase"
    gurobi_ok = _has_gurobi_wls_secrets()
    openai_ok = bool(st.secrets.get("OPENAI_API_KEY", ""))

    badges = (
        f'<span class="db-badge {"ok" if supabase_ok else "warn"}">{"✓" if supabase_ok else "!"} Supabase</span>'
        f'<span class="db-badge {"ok" if gurobi_ok else "warn"}">{"✓" if gurobi_ok else "!"} Gurobi WLS</span>'
        f'<span class="db-badge {"ok" if openai_ok else "warn"}">{"✓" if openai_ok else "!"} OpenAI</span>'
    )
    st.markdown(
        f"""
        <div class="db-header">
          <div>
            <h1>⚡ Data Center Energy Dispatch</h1>
            <p>Scenario-based optimization for PV · GT · SMR · ESS microgrids</p>
            <div style="margin-top:.6rem">{badges}</div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:1.5rem">🏭</div>
            <div>LangGraph Agent</div>
            <div>Gurobi Optimizer</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _has_gurobi_wls_secrets():
    return all(
        st.secrets.get(key, "")
        for key in ("GRB_WLSACCESSID", "GRB_WLSSECRET", "GRB_LICENSEID")
    )


# ─────────────────────────────────────────
#  Store / secrets
# ─────────────────────────────────────────

def get_supabase_store():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", st.secrets.get("SUPABASE_ANON_KEY", ""))
    store = SupabaseStore(url=url, key=key)
    if store.enabled:
        return store, "supabase"
    return store, "local"


def configure_runtime_secrets():
    openai_key = st.secrets.get("OPENAI_API_KEY", "")
    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key

    gurobi_keys = {
        "WLSACCESSID": st.secrets.get("GRB_WLSACCESSID", ""),
        "WLSSECRET": st.secrets.get("GRB_WLSSECRET", ""),
        "LICENSEID": st.secrets.get("GRB_LICENSEID", ""),
    }
    if all(gurobi_keys.values()):
        for key, value in gurobi_keys.items():
            os.environ[key] = str(value)
            os.environ[f"GRB_{key}"] = str(value)
        license_path = Path("/tmp/gurobi.lic")
        license_path.write_text(
            "\n".join(f"{key}={value}" for key, value in gurobi_keys.items()) + "\n",
            encoding="utf-8",
        )
        os.environ["GRB_LICENSE_FILE"] = str(license_path)


def get_graph():
    return build_graph()


def available_dispatch_steps(start_row, interval_minutes):
    load_path = Path("datacenter_load/dc_profile_15min_ED.csv")
    pv_path = Path("datacenter_load/pv_profile_15min_ED.csv")
    try:
        load_rows = pd.read_csv(load_path).dropna(how="all").shape[0]
        pv_rows = pd.read_csv(pv_path).dropna(how="all").shape[0]
        base_rows = max(1, min(load_rows, pv_rows) - int(start_row))
    except Exception:
        base_rows = 96
    aggregation_factor = max(1, int(interval_minutes) // 15)
    return max(1, base_rows // aggregation_factor)


SCENARIO_DEFAULTS = {
    "start_row": 0,
    "interval_minutes": 15,
    "time_steps": 96,
    "gt_count": 2,
    "gt_min": 85.0,
    "gt_max": 170.0,
    "gt_cost": 0.03,
    "smr_min": 91.0,
    "smr_max": 121.0,
    "smr_cost": 0.002,
    "ess_capacity_mwh": 160.0,
    "ess_power_mw": 40.0,
    "grid_import_limit_mw": 0.0,
    "tariff_season": "auto",
}


def init_scenario_state():
    for key, value in SCENARIO_DEFAULTS.items():
        st.session_state.setdefault(f"scenario_{key}", value)
    st.session_state.setdefault("scenario_nl_prompt", "")

    # Applied here (before any form widget is instantiated) so Streamlit allows
    # writing to widget-keyed session state.
    if st.session_state.pop("_reset_scenario", False):
        for key, value in SCENARIO_DEFAULTS.items():
            st.session_state[f"scenario_{key}"] = value
        st.session_state["scenario_nl_prompt"] = ""

    pending = st.session_state.pop("_pending_scenario", None)
    if pending:
        apply_scenario_draft(pending)

    if st.session_state.pop("_clear_nl", False):
        st.session_state["scenario_nl_prompt"] = ""


def apply_scenario_draft(draft):
    draft = sanitize_scenario_draft(draft)
    for key in SCENARIO_DEFAULTS:
        if key in draft and draft[key] is not None:
            st.session_state[f"scenario_{key}"] = draft[key]


def sanitize_scenario_draft(draft):
    cleaned = {}
    if not isinstance(draft, dict):
        return cleaned

    int_fields = {"start_row", "interval_minutes", "time_steps", "gt_count"}
    float_fields = set(SCENARIO_DEFAULTS) - int_fields

    for key, value in draft.items():
        if key not in SCENARIO_DEFAULTS or value in ("", None):
            continue
        if key == "tariff_season":
            season = str(value).strip().lower().replace(" ", "_")
            season = {"spring": "spring_fall", "fall": "spring_fall",
                      "autumn": "spring_fall"}.get(season, season)
            if season in {"auto", "summer", "spring_fall", "winter"}:
                cleaned[key] = season
            continue
        try:
            if key in int_fields:
                value = int(value)
            elif key in float_fields:
                value = float(value)
        except (TypeError, ValueError):
            continue

        if key == "interval_minutes" and value not in (15, 30, 60):
            continue
        if key == "time_steps" and not (4 <= value <= 672):
            continue
        if key == "gt_count" and not (1 <= value <= 20):
            continue
        if key in {"gt_min", "gt_max", "smr_min", "smr_max"} and value < 10:
            continue
        if key in {"gt_cost", "smr_cost"} and value <= 0:
            continue
        if key in {"ess_capacity_mwh", "ess_power_mw"} and value <= 0:
            continue
        if key == "grid_import_limit_mw" and value < 0:
            continue
        cleaned[key] = value

    return cleaned


def draft_config_from_natural_language(text):
    if not text.strip():
        return {}

    allowed_keys = list(SCENARIO_DEFAULTS.keys())
    system_prompt = (
        "Extract an energy dispatch scenario from the user's natural language. "
        "Return only a JSON object using these keys when present: "
        f"{', '.join(allowed_keys)}. "
        "Use MW for power, MWh for energy, minutes for interval_minutes. "
        "Only include values that are explicitly stated by the user. "
        "For example, '2 gas turbines' means gt_count=2 only; it does not imply gt_min or gt_max. "
        "Use 0 for grid_import_limit_mw only when the user explicitly says the grid is unlimited. "
        "Do not invent values."
    )
    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        content = resp.choices[0].message.content or "{}"
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        return sanitize_scenario_draft(json.loads(match.group(0) if match else content))
    except Exception:
        return sanitize_scenario_draft(draft_config_with_regex(text))


def draft_config_with_regex(text):
    draft = {}
    lower = text.lower()

    gt_match = re.search(r"(?:gt|gas turbine|가스터빈)\D{0,12}(\d+)\s*(?:대|unit|units)?", lower)
    if gt_match:
        draft["gt_count"] = int(gt_match.group(1))

    ess_match = re.search(r"(\d+(?:\.\d+)?)\s*mwh\s*/\s*(\d+(?:\.\d+)?)\s*mw", lower)
    if ess_match:
        draft["ess_capacity_mwh"] = float(ess_match.group(1))
        draft["ess_power_mw"] = float(ess_match.group(2))

    grid_match = re.search(r"(?:grid|계통|수전).{0,20}?(\d+(?:\.\d+)?)\s*mw", lower)
    if grid_match:
        draft["grid_import_limit_mw"] = float(grid_match.group(1))

    interval_match = re.search(r"(15|30|60)\s*(?:min|minute|분)", lower)
    if interval_match:
        draft["interval_minutes"] = int(interval_match.group(1))

    return draft


# ─────────────────────────────────────────
#  Scenario form
# ─────────────────────────────────────────

def scenario_form():
    init_scenario_state()
    st.markdown('<div class="section-card"><h2>🎛️ Scenario Configuration</h2>', unsafe_allow_html=True)

    with st.expander("Natural-language scenario draft", expanded=False):
        nl_prompt = st.text_area(
            "Scenario request",
            value="",
            placeholder="예: GT 1대, SMR 91-121MW, ESS 160MWh/40MW, grid cap 30MW로 실행해줘.",
            height=80,
            key="scenario_nl_prompt",
        )
        draft_col, reset_col = st.columns(2)
        with draft_col:
            if st.button("Draft settings from text", use_container_width=True):
                draft = draft_config_from_natural_language(nl_prompt)
                apply_scenario_draft(draft)
                st.success("Scenario settings were drafted. Review the fields below before running.")
        with reset_col:
            if st.button("🔄 New scenario (reset to defaults)", use_container_width=True):
                st.session_state["_reset_scenario"] = True
                st.rerun()

    scenario_col1, scenario_col2, scenario_col3, scenario_col4 = st.columns([2, 1, 1, 1])
    with scenario_col1:
        name = st.text_input("Scenario name", value="Data center ED run")
    with scenario_col2:
        start_row = st.number_input("Start row", min_value=0, max_value=100000, step=1, key="scenario_start_row")
    with scenario_col3:
        interval_default = st.session_state.get("scenario_interval_minutes", 15)
        interval_index = [15, 30, 60].index(interval_default) if interval_default in [15, 30, 60] else 0
        interval_minutes = st.selectbox(
            "Resolution",
            options=[15, 30, 60],
            index=interval_index,
            format_func=lambda v: f"{v} min",
            key="scenario_interval_minutes",
        )
    with scenario_col4:
        default_steps = int(24 * 60 / interval_minutes)
        max_steps = available_dispatch_steps(start_row, interval_minutes)
        st.session_state["scenario_time_steps"] = min(int(st.session_state.get("scenario_time_steps", default_steps)), max_steps)
        time_steps = st.number_input("Dispatch intervals", min_value=1, max_value=max_steps, step=1, key="scenario_time_steps")

    with st.expander("Scenario memo", expanded=False):
        description = st.text_area(
            "Description",
            value="PV, SMR, GT, ESS를 활용해 선택한 시간 해상도로 데이터센터 경제급전을 수행한다.",
            height=80,
        )

    st.markdown("---")
    gen_col1, gen_col2, gen_col3, gen_col4 = st.columns(4)
    with gen_col1:
        gt_count = st.number_input("GT count", min_value=1, max_value=20, step=1, key="scenario_gt_count")
    with gen_col2:
        gt_min = st.number_input("GT min MW", min_value=0.0, step=5.0, key="scenario_gt_min")
    with gen_col3:
        gt_max = st.number_input("GT max MW", min_value=0.0, step=5.0, key="scenario_gt_max")
    with gen_col4:
        gt_cost = st.number_input("GT cost coeff", min_value=0.0, step=0.001, format="%.3f", key="scenario_gt_cost")

    smr_col1, smr_col2, smr_col3 = st.columns(3)
    with smr_col1:
        smr_min = st.number_input("SMR min MW", min_value=0.0, step=1.0, key="scenario_smr_min")
    with smr_col2:
        smr_max = st.number_input("SMR max MW", min_value=0.0, step=1.0, key="scenario_smr_max")
    with smr_col3:
        smr_cost = st.number_input("SMR cost coeff", min_value=0.0, step=0.001, format="%.3f", key="scenario_smr_cost")

    st.markdown("---")
    storage_col1, storage_col2, grid_col, tariff_col = st.columns(4)
    with storage_col1:
        ess_capacity_mwh = st.number_input("ESS capacity MWh", min_value=0.0, step=10.0, key="scenario_ess_capacity_mwh")
    with storage_col2:
        ess_power_mw = st.number_input("ESS max power MW", min_value=0.0, step=5.0, key="scenario_ess_power_mw")
    with grid_col:
        grid_import_limit_mw = st.number_input(
            "Grid import cap MW (0 = unbounded)",
            min_value=0.0,
            step=10.0,
            key="scenario_grid_import_limit_mw",
        )
    with tariff_col:
        tariff_options = ["auto", "summer", "spring_fall", "winter"]
        tariff_default = st.session_state.get("scenario_tariff_season", "auto")
        if tariff_default not in tariff_options:
            tariff_default = "auto"
        tariff_season = st.selectbox(
            "TOU season",
            options=tariff_options,
            index=tariff_options.index(tariff_default),
            format_func=lambda v: {"auto": "Auto (by date)", "summer": "Summer",
                                   "spring_fall": "Spring/Fall", "winter": "Winter"}[v],
            key="scenario_tariff_season",
        )

    st.markdown("</div>", unsafe_allow_html=True)

    config = {
        "start_row": int(start_row),
        "time_steps": int(time_steps),
        "interval_minutes": int(interval_minutes),
        "gt_count": int(gt_count),
        "gt_min": gt_min,
        "gt_max": gt_max,
        "gt_cost": gt_cost,
        "smr_min": smr_min,
        "smr_max": smr_max,
        "smr_cost": smr_cost,
        "ess_capacity_mwh": ess_capacity_mwh,
        "ess_power_mw": ess_power_mw,
        "grid_import_limit_mw": None if grid_import_limit_mw == 0 else grid_import_limit_mw,
        "tariff_season": None if tariff_season == "auto" else tariff_season,
    }
    return name, description, config


# ─────────────────────────────────────────
#  Workflow runner
# ─────────────────────────────────────────

def run_workflow(name, description, config, store):
    if not store.enabled:
        raise RuntimeError("Supabase secrets가 설정되지 않았습니다. 서버에서는 SUPABASE_URL과 SUPABASE_ANON_KEY 또는 SUPABASE_SERVICE_ROLE_KEY가 필요합니다.")

    scenario_row = None
    scenario_row = store.insert_scenario(name=name, description=description, config=config)

    # The Formulation Agent parses this natural-language request into parameters;
    # when empty, it falls back to the structured form config.
    nl_request = (st.session_state.get("scenario_nl_prompt") or "").strip()

    initial_state = {
        "problem_text": nl_request,
        "scenario_config": config,
        "solution_output": None,
        "explanation": None,
    }
    result = get_graph().invoke(initial_state)
    solution_data = result.get("solution_output")
    params = result.get("params")
    if not solution_data or not params:
        available_keys = ", ".join(sorted(result.keys()))
        if result.get("solver_error"):
            detail = result["solver_error"]
        elif not params:
            detail = "Formulation did not return EDParams."
        else:
            detail = "Solver did not return solution_output."
        raise RuntimeError(f"{detail} State keys: {available_keys}")

    rows = solution_rows(solution_data, params)
    metrics = summary_metrics(solution_data, params)

    with tempfile.TemporaryDirectory() as tmp_dir:
        image_path = Path(tmp_dir) / "optimization_result.png"
        pdf_path = Path(tmp_dir) / "Final_Report.pdf"
        plot_results(solution_data, params, image_path)
        if not image_path.exists():
            raise RuntimeError("Graph image was not generated.")
        create_pdf_report(result.get("explanation"), image_path, pdf_path, metrics=metrics)
        image_bytes = image_path.read_bytes()
        pdf_bytes = pdf_path.read_bytes()

    run_row = None
    scenario_id = scenario_row.get("id") if scenario_row else None
    run_row = store.insert_run(
        scenario_id=scenario_id,
        status="success",
        metrics=metrics,
        result_table=rows,
        report_text=result.get("explanation") or "",
    )

    # Write the resolved scenario back to the form so the next request builds on
    # it (e.g. "add one gas turbine" accumulates); the NL box is cleared so a
    # relative command applies once. "New scenario" resets to defaults instead.
    resolved_config = result.get("scenario_config")
    if isinstance(resolved_config, dict):
        st.session_state["_pending_scenario"] = resolved_config
        st.session_state["_clear_nl"] = True

    return {
        "scenario": scenario_row,
        "run": run_row,
        "rows": rows,
        "metrics": metrics,
        "report": result.get("explanation") or "",
        "image_bytes": image_bytes,
        "pdf_bytes": pdf_bytes,
    }


# ─────────────────────────────────────────
#  KPI cards
# ─────────────────────────────────────────

def render_kpi_cards(metrics):
    cards = [
        {"label": "Total Cost",        "value": f"{metrics.get('total_cost', 0):,.0f}",       "unit": "KRW", "sub": "Optimized system cost", "accent": "#2563eb"},
        {"label": "PV Renewable Share", "value": f"{metrics.get('pv_share', 0):.1f}",          "unit": "%",   "sub": "of total supply",       "accent": "#10b981"},
        {"label": "Grid Import",        "value": f"{metrics.get('total_grid', 0):,.1f}",       "unit": "MWh", "sub": "External grid usage",   "accent": "#8b5cf6"},
        {"label": "Generator Output",   "value": f"{metrics.get('total_generation', 0):,.1f}", "unit": "MWh", "sub": "GT + SMR combined",     "accent": "#f59e0b"},
        {"label": "Peak Demand",        "value": f"{metrics.get('peak_supply', 0):,.1f}",      "unit": "MW",  "sub": f"@ {metrics.get('peak_time', '-')}", "accent": "#ef4444"},
    ]
    cols = st.columns(5)
    for col, card in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card" style="--accent:{card['accent']}">
                  <div class="kpi-label">{card['label']}</div>
                  <div><span class="kpi-value">{card['value']}</span><span class="kpi-unit">{card['unit']}</span></div>
                  <div class="kpi-sub">{card['sub']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────
#  Report renderer
# ─────────────────────────────────────────

_SECTION_META = [
    (r"executive summary",               "exec",     "📋 Executive Summary"),
    (r"system configuration",            "config",   "⚙️ System Configuration"),
    (r"cost structure",                  "cost",     "💰 Cost Structure"),
    (r"dispatch strategy",               "dispatch", "📊 Dispatch Strategy"),
    (r"tou.based operation|time.of.use", "tou",      "🕐 TOU Operation Strategy"),
    (r"assessment.*recommendation|recommendation", "rec",   "💡 Recommendations"),
    (r"data limitation|limitation|assumption",     "limit", "⚠️ Limitations & Assumptions"),
]


def _classify_section(title: str) -> tuple[str, str]:
    t = title.lower()
    for pattern, cls, label in _SECTION_META:
        if re.search(pattern, t):
            return cls, label
    return "exec", title


def render_ai_report(report_text: str):
    st.markdown('<div class="section-card"><h2>🤖 AI Analysis Report</h2>', unsafe_allow_html=True)
    raw_sections = re.split(r'\n(?=#{1,3}\s)', report_text.strip())
    blocks_html = ""
    for chunk in raw_sections:
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r'^(#{1,3})\s+(.*)', chunk)
        if m:
            title, body_raw = m.group(2).strip(), chunk[m.end():].strip()
        else:
            title, body_raw = "Summary", chunk
        cls, display_title = _classify_section(title)
        blocks_html += f'<div class="report-block {cls}"><h3>{display_title}</h3>{_body_to_html(body_raw)}</div>'
    st.markdown(blocks_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _body_to_html(text: str) -> str:
    lines = text.splitlines()
    html_parts = []
    list_open = False
    for line in lines:
        line = line.strip()
        if not line:
            if list_open:
                html_parts.append("</ul>")
                list_open = False
            continue
        is_bullet = line.startswith("- ") or line.startswith("* ")
        if is_bullet:
            if not list_open:
                html_parts.append("<ul>")
                list_open = True
            bullet_text = re.sub(r"[*]{2}(.*?)[*]{2}", r"<strong>\1</strong>", line[2:].strip())
            html_parts.append(f"<li>{bullet_text}</li>")
        else:
            if list_open:
                html_parts.append("</ul>")
                list_open = False
            paragraph_text = re.sub(r"[*]{2}(.*?)[*]{2}", r"<strong>\1</strong>", line)
            html_parts.append(f"<p>{paragraph_text}</p>")
    if list_open:
        html_parts.append("</ul>")
    return "\n".join(html_parts)


# ─────────────────────────────────────────
#  Result dashboard
# ─────────────────────────────────────────

def render_result(result):
    metrics = result.get("metrics") or {}

    st.markdown('<div class="section-card" style="padding:1.25rem 1.75rem;"><h2>📈 Key Performance Indicators</h2>', unsafe_allow_html=True)
    render_kpi_cards(metrics)
    st.markdown("</div>", unsafe_allow_html=True)

    chart_col, tou_col = st.columns([3, 2])
    with chart_col:
        st.markdown('<div class="section-card"><h2>⚡ Energy Dispatch Mix</h2>', unsafe_allow_html=True)
        st.image(result["image_bytes"], use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with tou_col:
        st.markdown('<div class="section-card"><h2>🕐 TOU Period Summary</h2>', unsafe_allow_html=True)
        _render_tou_table(result.get("rows", []))
        st.markdown("</div>", unsafe_allow_html=True)

    render_ai_report(result["report"])

    dl_col, _ = st.columns([1, 3])
    with dl_col:
        st.download_button(
            "⬇️ Download PDF Report",
            data=result["pdf_bytes"],
            file_name="data_center_energy_report.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )

    st.markdown('<div class="section-card"><h2>📋 Dispatch Table</h2>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(result["rows"]), use_container_width=True, height=320)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_tou_table(rows):
    if not rows:
        st.info("No dispatch data.")
        return
    df = pd.DataFrame(rows)
    gen_cols = [
        c for c in df.columns
        if c.endswith("_mw") and not c.startswith(("pv", "ess", "grid", "net", "managed", "balance"))
    ]

    def period_label(t):
        try:
            h = int(str(t).split(":")[-2]) if ":" in str(t) else int(str(t).split(" ")[-1].split(":")[0])
        except Exception:
            return "off"
        if 9 <= h < 12 or 13 <= h < 18:
            return "on"
        if 7 <= h < 9 or 12 <= h < 13 or 18 <= h < 21:
            return "mid"
        return "off"

    df["period"] = df["time"].apply(period_label)
    summary = df.groupby("period").agg(
        pv_mw=("pv_mw", "mean"),
        ess_mw=("ess_discharge_mw", "mean"),
        **{col: (col, "mean") for col in gen_cols},
    ).reset_index().sort_values("period", key=lambda s: s.map({"off": 0, "mid": 1, "on": 2}))

    period_badge = {
        "off": '<span class="badge-off">Off-Peak</span>',
        "mid": '<span class="badge-mid">Mid-Peak</span>',
        "on":  '<span class="badge-on">On-Peak</span>',
    }
    header = "<tr><th>Period</th><th>PV (MW)</th>"
    for col in gen_cols:
        header += f"<th>{col.replace('_mw','').upper()} (MW)</th>"
    header += "<th>ESS Dis (MW)</th></tr>"

    body = ""
    for _, row in summary.iterrows():
        cells = f"<td>{period_badge.get(row['period'], row['period'])}</td><td>{row['pv_mw']:.1f}</td>"
        for col in gen_cols:
            cells += f"<td>{row.get(col, 0):.1f}</td>"
        cells += f"<td>{row['ess_mw']:.1f}</td>"
        body += f"<tr>{cells}</tr>"

    st.markdown(
        f'<table class="tou-table"><thead>{header}</thead><tbody>{body}</tbody></table>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────
#  History tab
# ─────────────────────────────────────────

def render_history(store):
    if not store.enabled:
        st.error("Supabase secrets가 설정되지 않았습니다. 서버 Settings > Secrets에 SUPABASE_URL과 SUPABASE_ANON_KEY 또는 SUPABASE_SERVICE_ROLE_KEY를 추가하세요.")
        return
    try:
        runs = store.list_runs(limit=30)
    except Exception as exc:
        st.error(f"History 조회 실패: {exc}")
        return
    if not runs:
        st.info("저장된 실행 이력이 없습니다.")
        return

    options = {
        f"{row.get('created_at', '')} | {(row.get('scenarios') or {}).get('name', 'Untitled')} | {row.get('status', '')}": row
        for row in runs
    }
    selected = options[st.selectbox("Past runs", list(options.keys()))]
    metrics = selected.get("metrics") or {}
    if metrics:
        render_kpi_cards(metrics)
    st.json({"scenario": selected.get("scenarios"), "metrics": metrics,
             "status": selected.get("status"), "error": selected.get("error_message")})
    table = selected.get("result_table") or []
    if table:
        st.dataframe(pd.DataFrame(table), use_container_width=True, height=320)
    if selected.get("report_text"):
        render_ai_report(selected["report_text"])


# ─────────────────────────────────────────
#  Main
# ─────────────────────────────────────────

def main():
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False

    inject_css(st.session_state["dark_mode"])
    configure_runtime_secrets()
    store, store_mode = get_supabase_store()
    render_page_header(store_mode)

    # Theme toggle — right side of header area
    _, btn_col = st.columns([11, 1])
    with btn_col:
        label = "🌙 Dark" if not st.session_state["dark_mode"] else "☀️ Light"
        if st.button(label, use_container_width=True):
            st.session_state["dark_mode"] = not st.session_state["dark_mode"]
            st.rerun()

    run_tab, history_tab = st.tabs(["▶ Run", "🕘 History"])

    with run_tab:
        name, description, config = scenario_form()

        with st.expander("Current settings preview", expanded=False):
            st.dataframe(
                pd.DataFrame([{"parameter": k, "value": v} for k, v in config.items()]),
                use_container_width=True,
                hide_index=True,
            )

        if st.button("🚀 Run LangGraph Agent", type="primary", use_container_width=True):
            ran_ok = False
            try:
                with st.status("Running optimization workflow...", expanded=True) as status:
                    st.write("⏳ Saving scenario...")
                    st.write("⚙️ Solving dispatch with Gurobi...")
                    st.write("📊 Generating graph, report, and PDF...")
                    st.session_state["latest_result"] = run_workflow(name, description, config, store)
                    status.update(label="✅ Workflow completed", state="complete", expanded=False)
                ran_ok = True
            except Exception as exc:
                if store.enabled:
                    try:
                        store.insert_run(None, "failed", {}, [], "", error_message=str(exc))
                    except Exception:
                        pass
                st.error(f"실행 실패: {exc}")
            # Rerun outside the try so the resolved scenario is written back to the
            # form (applied in init_scenario_state before the widgets render).
            if ran_ok:
                st.rerun()

        if "latest_result" in st.session_state:
            render_result(st.session_state["latest_result"])

    with history_tab:
        render_history(store)


if __name__ == "__main__":
    main()
