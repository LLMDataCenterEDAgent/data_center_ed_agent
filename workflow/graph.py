# workflow/graph.py

from langgraph.graph import StateGraph, END
from state.base_state import AgentState

# 에이전트 클래스 임포트
from agents.parsing_agent import ParsingAgent
from agents.formulation_agent import FormulationAgent
from agents.solver_agent import SolverAgent
from agents.explanation_agent import ExplanationAgent

def build_graph():
    # 1. 그래프 초기화
    workflow = StateGraph(AgentState)

    # 2. 에이전트 인스턴스 생성
    parser = ParsingAgent()
    formulator = FormulationAgent()
    solver = SolverAgent()
    explainer = ExplanationAgent()

    # 3. 노드 정의 (클래스의 .run 메서드 연결)
    workflow.add_node("parse", parser.run)
    workflow.add_node("formulate", formulator.run)
    workflow.add_node("solve", solver.run)
    workflow.add_node("explain", explainer.run)

    # 4. 엣지 연결 (순차 실행)
    # parse -> formulate -> solve -> explain -> END
    workflow.set_entry_point("parse")
    workflow.add_edge("parse", "formulate")
    workflow.add_edge("formulate", "solve")
    workflow.add_edge("solve", "explain")
    workflow.add_edge("explain", END)

    # 5. 컴파일
    return workflow.compile()