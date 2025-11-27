def solver_agent_node(state: EDAgentState) -> EDAgentState:
    model = state.model_code
    solver = SolverFactory("glpk")
    result = solver.solve(model)

    state.solution_summary = str(result.solver.status)
    state.logs.append("SolverAgent: solved.")
    return state
