# core/graph.py

from langgraph.graph import StateGraph, START, END
from core.state import EDAgentState
from agents.data_extractor_agent import data_extractor_node
from agents.constraint_agent import constraint_agent_node
from agents.formulation_agent import formulation_agent_node
from agents.solver_agent import solver_agent_node


def build_graph():
    graph = StateGraph(EDAgentState)

    graph.add_node("extractor", data_extractor_node)
    graph.add_node("constraint", constraint_agent_node)
    graph.add_node("formulation", formulation_agent_node)
    graph.add_node("solver", solver_agent_node)

    graph.add_edge(START, "extractor")
    graph.add_edge("extractor", "constraint")
    graph.add_edge("constraint", "formulation")
    graph.add_edge("formulation", "solver")

    # ❗ Solver는 항상 종료로 보내기 (루프 금지)
    graph.add_edge("solver", END)

    return graph
