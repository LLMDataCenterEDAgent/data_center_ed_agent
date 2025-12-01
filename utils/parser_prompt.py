# utils/parser_prompt.py

PARSING_SYSTEM_PROMPT = """
You MUST output ONLY a valid JSON object with the structure:

{
  "generators": {
    "G1": {"a": float, "b": float, "c": float, "p_min": float, "p_max": float},
    "G2": {"a": float, "b": float, "c": float, "p_min": float, "p_max": float}
  },
  "demand": float
}

Rules:
- Never add explanations.
- Never output keys other than the above structure.
- Do NOT change the key names.
- If values are ambiguous, infer the most reasonable numeric value.
- Output ONLY JSON. No surrounding text.
"""
