# workflow/graph.py

from langgraph.graph import StateGraph
from state.base_state import EDState

from agents.parsing_agent import parse_problem
from agents.formulation_agent import formulate
from agents.solver_agent import solve_ed
from agents.explanation_agent import explain_solution


def parsing_node(state):
    print("\n===== PROBLEM TEXT RECEIVED BY LLM =====")
    print(state["problem_text"])
    print("========================================\n")

    params = parse_problem(state["problem_text"])
    print("\n===== PARSING RESULT =====")
    print(params)
    print("==========================\n")

    state["params"] = params
    return state


def formulation_node(state):
    state["formulated"] = formulate(state["params"])
    return state

def solver_node(state):
    sol = solve_ed(state["formulated"], method="analytic")
    state["solution"] = sol
    return state

def explanation_node(state):
    explain = explain_solution(state["formulated"], state["solution"])
    state["explanation"] = explain
    return state


def build_graph():
    graph = StateGraph(EDState)

    graph.add_node("parse", parsing_node)
    graph.add_node("formulate", formulation_node)
    graph.add_node("solve", solver_node)
    graph.add_node("explain", explanation_node)

    graph.set_entry_point("parse")
    graph.add_edge("parse", "formulate")
    graph.add_edge("formulate", "solve")
    graph.add_edge("solve", "explain")

    return graph.compile()
