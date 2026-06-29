import os
import re
from pathlib import Path


def load_streamlit_secrets_into_env(base_dir=None):
    """Load simple key/value Streamlit secrets for non-Streamlit scripts."""
    root = Path(base_dir) if base_dir else Path.cwd()
    secrets_path = root / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return False

    loaded = False
    text = secrets_path.read_text(encoding="utf-8", errors="ignore")
    for key in [
        "OPENAI_API_KEY",
        "OPENAI_ADMIN_KEY",
        "GRB_WLSACCESSID",
        "GRB_WLSSECRET",
        "GRB_LICENSEID",
    ]:
        if os.environ.get(key):
            continue
        match = re.search(rf"^\s*{re.escape(key)}\s*=\s*['\"]([^'\"]+)['\"]", text, flags=re.MULTILINE)
        if match:
            os.environ[key] = match.group(1)
            loaded = True

    return loaded
