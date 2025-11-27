# core/config.py

DEFAULT_MODEL_NAME = "gpt-4o-mini"

# For LLM output validation
REQUIRED_CONSTRAINT_FIELDS = [
    "use_smr",
    "use_mgt",
    "ess_mode"
]