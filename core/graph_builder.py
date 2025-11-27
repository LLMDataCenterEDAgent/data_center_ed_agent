# core/graph_builder.py
from langgraph.graph import StateGraph
from core.state import EDState

from scenario_engine.scenario_generator import scenario_node
from scenario_engine.scenario_to_data import data_dict_node
from agents.constraint_agent import constraint_agent_node
from models.ed_model import model_builder_node
from agents.solver_agent import solver_node
from agents.analysis_agent import analysis_agent_node


def build_graph():

    graph = StateGraph(EDState)

    graph.add_node("scenario", scenario_node)
    graph.add_node("data_dict", data_dict_node)
    graph.add_node("constraint", constraint_agent_node)
    graph.add_node("model", model_builder_node)
    graph.add_node("solver", solver_node)
    graph.add_node("analysis", analysis_agent_node)

    graph.set_entry_point("scenario")

    graph.add_edge("scenario", "data_dict")
    graph.add_edge("data_dict", "constraint")
    graph.add_edge("constraint", "model")
    graph.add_edge("model", "solver")
    graph.add_edge("solver", "analysis")

    return graph.compile()