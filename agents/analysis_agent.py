# agents/analysis_agent.py
from utils.llm_client import get_llm_client
client = get_llm_client()

def analysis_agent_node(state):

    results = state["solution"]

    prompt = f"""
    Analyze this ED optimization result:
    {results}

    Provide:
    - Key cost drivers
    - ESS behavior
    - PV utilization
    - Recommended next scenario strategy
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    state["analysis"] = resp.choices[0].message["content"]
    return state