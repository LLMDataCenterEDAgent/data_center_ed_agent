import tempfile
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from services.local_store import LocalStore
from services.supabase_store import SupabaseStore
from ui.reporting import create_pdf_report, plot_results, solution_rows, summary_metrics
from workflow.graph import build_graph


st.set_page_config(page_title="Data Center ED Agent", page_icon="DC", layout="wide")


def get_supabase_store():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", st.secrets.get("SUPABASE_ANON_KEY", ""))
    store = SupabaseStore(url=url, key=key)
    if store.enabled:
        return store, "supabase"
    return LocalStore(), "local"


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
        license_path = Path("/tmp/gurobi.lic")
        license_path.write_text(
            "\n".join(f"{key}={value}" for key, value in gurobi_keys.items()) + "\n",
            encoding="utf-8",
        )
        os.environ["GRB_LICENSE_FILE"] = str(license_path)
        print(f"Gurobi WLS license configured at {license_path}")


def get_graph():
    return build_graph()


def scenario_form():
    name = st.text_input("Scenario name", value="Data center ED run")
    description = st.text_area(
        "Scenario description",
        value="PV, SMR, GT, ESS를 활용해 15분 단위 데이터센터 경제급전을 수행한다.",
        help="Supabase History에서 실행 목적을 구분하기 위한 메모입니다. 현재 최적화 계산값은 아래 숫자 입력값으로 결정됩니다.",
        height=100,
    )

    time_col1, time_col2 = st.columns(2)
    with time_col1:
        start_row = st.number_input("Start row", min_value=0, max_value=100000, value=0, step=1)
    with time_col2:
        time_steps = st.number_input("15-min steps", min_value=4, max_value=96, value=96, step=1)

    st.subheader("Generator")
    gen_col1, gen_col2, gen_col3 = st.columns(3)
    with gen_col1:
        gt_count = st.number_input("GT count", min_value=1, max_value=20, value=2, step=1)
        gt_min = st.number_input("GT min MW", min_value=0.0, value=85.0, step=5.0)
        gt_max = st.number_input("GT max MW", min_value=0.0, value=170.0, step=5.0)
    with gen_col2:
        gt_cost = st.number_input("GT cost coefficient", min_value=0.0, value=0.03, step=0.001, format="%.3f")
        smr_min = st.number_input("SMR min MW", min_value=0.0, value=91.0, step=1.0)
        smr_max = st.number_input("SMR max MW", min_value=0.0, value=121.0, step=1.0)
    with gen_col3:
        smr_cost = st.number_input("SMR cost coefficient", min_value=0.0, value=0.002, step=0.001, format="%.3f")
        ess_capacity_mwh = st.number_input("ESS capacity MWh", min_value=0.0, value=160.0, step=10.0)
        ess_power_mw = st.number_input("ESS max power MW", min_value=0.0, value=40.0, step=5.0)

    config = {
        "start_row": int(start_row),
        "time_steps": int(time_steps),
        "gt_count": int(gt_count),
        "gt_min": gt_min,
        "gt_max": gt_max,
        "gt_cost": gt_cost,
        "smr_min": smr_min,
        "smr_max": smr_max,
        "smr_cost": smr_cost,
        "ess_capacity_mwh": ess_capacity_mwh,
        "ess_power_mw": ess_power_mw,
    }
    return name, description, config


def run_workflow(name, description, config, store):
    scenario_row = None
    if store.enabled:
        scenario_row = store.insert_scenario(name=name, description=description, config=config)

    initial_state = {
        "problem_text": description,
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
            raise RuntimeError("Graph image was not generated because the optimization result is empty.")
        create_pdf_report(result.get("explanation"), image_path, pdf_path)
        image_bytes = image_path.read_bytes()
        pdf_bytes = pdf_path.read_bytes()

    run_row = None
    if store.enabled:
        scenario_id = scenario_row.get("id") if scenario_row else None
        run_row = store.insert_run(
            scenario_id=scenario_id,
            status="success",
            metrics=metrics,
            result_table=rows,
            report_text=result.get("explanation") or "",
        )

    return {
        "scenario": scenario_row,
        "run": run_row,
        "rows": rows,
        "metrics": metrics,
        "report": result.get("explanation") or "",
        "image_bytes": image_bytes,
        "pdf_bytes": pdf_bytes,
    }


def render_metric_bar(metrics):
    items = [
        ("Total Cost", f"{metrics.get('total_cost', 0):,.0f}", "KRW"),
        ("PV Share", f"{metrics.get('pv_share', 0):.1f}", "%"),
        ("Grid", f"{metrics.get('total_grid', 0):,.1f}", "MW"),
        ("Generation", f"{metrics.get('total_generation', 0):,.1f}", "MW"),
        ("Peak", f"{metrics.get('peak_supply', 0):,.1f}", "MW"),
    ]
    cols = st.columns(5)
    for col, (label, value, unit) in zip(cols, items):
        with col:
            st.caption(label)
            st.markdown(f"**{value}** `{unit}`")


def render_result(result):
    metrics = result.get("metrics") or {}
    render_metric_bar(metrics)

    st.subheader("Result table")
    st.dataframe(pd.DataFrame(result["rows"]), use_container_width=True, height=360)

    st.subheader("Graph")
    st.image(result["image_bytes"], use_container_width=True)

    st.subheader("Report")
    st.markdown(result["report"])
    st.download_button(
        "Download PDF",
        data=result["pdf_bytes"],
        file_name="data_center_energy_report.pdf",
        mime="application/pdf",
        use_container_width=True,
    )


def render_history(store):
    if not store.enabled:
        st.info("Supabase secrets가 설정되면 과거 실행 이력이 여기에 표시됩니다.")
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
    selected_label = st.selectbox("Past runs", list(options.keys()))
    selected = options[selected_label]
    st.json(
        {
            "scenario": selected.get("scenarios"),
            "metrics": selected.get("metrics"),
            "status": selected.get("status"),
            "error": selected.get("error_message"),
        }
    )
    table = selected.get("result_table") or []
    if table:
        st.dataframe(pd.DataFrame(table), use_container_width=True, height=320)
    if selected.get("report_text"):
        st.markdown(selected["report_text"])


def main():
    configure_runtime_secrets()
    st.title("Data Center Energy Dispatch Agent")

    store, store_mode = get_supabase_store()
    if store_mode == "supabase":
        st.success("Supabase 연결 설정이 감지되었습니다.")
    else:
        st.info("Supabase secrets가 없어 로컬 SQLite에 실행 이력을 저장합니다.")

    run_tab, history_tab = st.tabs(["Run", "History"])
    with run_tab:
        st.subheader("Scenario setup")
        name, description, config = scenario_form()

        with st.expander("Current settings", expanded=False):
            st.dataframe(
                pd.DataFrame(
                    [{"parameter": key, "value": value} for key, value in config.items()]
                ),
                use_container_width=True,
                hide_index=True,
            )

        if st.button("Run LangGraph agent", type="primary"):
            try:
                with st.spinner("LangGraph agent 실행 중..."):
                    st.session_state["latest_result"] = run_workflow(
                        name,
                        description,
                        config,
                        store,
                    )
                st.success("실행이 완료되었습니다.")
            except Exception as exc:
                if store.enabled:
                    try:
                        store.insert_run(None, "failed", {}, [], "", error_message=str(exc))
                    except Exception:
                        pass
                st.error(f"실행 실패: {exc}")

        if "latest_result" in st.session_state:
            render_result(st.session_state["latest_result"])

    with history_tab:
        render_history(store)


if __name__ == "__main__":
    main()
