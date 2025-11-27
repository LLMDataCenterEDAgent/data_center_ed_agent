# core/graph.py

from langgraph.graph import StateGraph, START, END
from core.state import EDAgentState
from agents.data_extractor_agent import data_extractor_node
from agents.constraint_agent import constraint_agent_node
from agents.formulation_agent import formulation_agent_node
from agents.solver_agent import solver_agent_node
from agents.solution_explain_agent import solution_explain_node
from agents.scenario_llm_agent import scenario_llm_node
from agents.pyomo_builder_agent import pyomo_builder_node   

def build_graph():
    graph = StateGraph(EDAgentState)

    graph.add_node("scenario", scenario_llm_node)
    graph.add_node("extractor", data_extractor_node)
    graph.add_node("builder", pyomo_builder_node)
    graph.add_node("solver", solver_agent_node)
    graph.add_node("explain", solution_explain_node)

    graph.add_edge(START, "scenario")
    graph.add_edge("scenario", "extractor")
    graph.add_edge("extractor", "builder")
    graph.add_edge("builder", "solver")
    graph.add_edge("solver", "explain")
    graph.add_edge("explain", END)

    return graph
