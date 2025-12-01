from workflow.graph import build_graph

if __name__ == "__main__":
    graph = build_graph()

    problem_text = """
    비용함수는 F1 = 0.001P1^2 + 0.5P1 + 3,
    F2 = 0.002P2^2 + 0.3P2 + 5.
    발전기1 출력은 100~280, 발전기2는 150~300.
    총 수요는 500MW이다.
    """

    initial_state = {
        "problem_text": problem_text,
        "params": None,
        "formulated": None,
        "solution": None,
        "explanation": None,
    }

    result = graph.invoke(initial_state)

    print("------ PARSED PARAMS ------")
    print(result["params"]) 
    print(result.get("params"))
    print("------ SOLUTION ------")
    print(result.get("solution"))
    print("------ EXPLANATION ------")
    print(result.get("explanation"))
