# agents/constraint_agent.py
from utils.llm_client import get_llm_client
client = get_llm_client()

def constraint_agent_node(state):

    scenario = state["scenario"]

    prompt = f"""
    You are an energy-dispatch policy agent.

    Given:
    Load curve: {scenario["load_curve"]}
    PV profile: {scenario["pv_profile"]}

    Propose high-level constraints to reduce energy cost.
    Return ONLY JSON with fields:
    {{
        "use_smr": true/false,
        "use_mgt": true/false,
        "ess_mode": "aggressive" | "normal" | "conservative"
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    config = eval(response.choices[0].message["content"])
    state["constraint_config"] = config
    return state