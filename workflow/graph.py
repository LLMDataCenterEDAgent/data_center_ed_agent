# workflow/graph.py

from langgraph.graph import StateGraph, END
# [확인] base_state에서 AgentState를 가져오는지 꼭 확인하세요!
from state.base_state import AgentState 

# 에이전트들 임포트
from agents.parsing_agent import ParsingAgent
from agents.formulation_agent import FormulationAgent
from agents.solver_agent import SolverAgent
from agents.explanation_agent_v2 import ExplanationAgent


def route_after_solve(state: AgentState):
    if state.get("solver_error"):
        attempts = int(state.get("correction_attempts", 0) or 0)
        max_attempts = int(state.get("max_correction_attempts", 2) or 2)
        if attempts < max_attempts:
            return "retry"
        return "end"
    return "explain"

def build_graph():
    # 1. 그래프 초기화
    # [확인] StateGraph 안에 AgentState를 넣어야 합니다.
    workflow = StateGraph(AgentState)

    # 2. 에이전트 생성
    parser = ParsingAgent()
    formulator = FormulationAgent()
    solver = SolverAgent()
    explainer = ExplanationAgent()

    # 3. 노드 연결
    workflow.add_node("parse", parser.run)
    workflow.add_node("formulate", formulator.run)
    workflow.add_node("solve", solver.run)
    workflow.add_node("explain", explainer.run)

    # 4. 흐름 연결
    workflow.set_entry_point("parse")
    workflow.add_edge("parse", "formulate")
    workflow.add_edge("formulate", "solve")
    workflow.add_conditional_edges(
        "solve",
        route_after_solve,
        {
            "retry": "formulate",
            "explain": "explain",
            "end": END,
        },
    )
    workflow.add_edge("explain", END)

    return workflow.compile()
