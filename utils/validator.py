PARSING_SYSTEM_PROMPT = """
You MUST output ONLY a valid JSON object with this exact structure:

{
  "generators": {
    "G1": {"a": float, "b": float, "c": float, "p_min": float, "p_max": float},
    "G2": {"a": float, "b": float, "c": float, "p_min": float, "p_max": float}
  },
  "demand": float
}

RULES:
- "demand" MUST be a numeric value extracted from the text.
- If demand is missing, you MUST infer it from phrases like "총 수요", "load", "demand", "필요 전력".
- Do NOT leave demand as null under ANY circumstances.
- If multiple numbers appear, choose the one described as total/required power.
- If ambiguous, choose the most likely demand.
- Output ONLY raw JSON. No explanations, no comments, no markdown.
"""
