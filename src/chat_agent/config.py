"""Application constants and startup checks."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"

HOST = "127.0.0.1"  # localhost only (AC-2)
PORT = 8000

MODEL = "claude-sonnet-5-5"
MAX_TOOL_CALLS = 10  # per user message (AC-11)
MAX_READ_BYTES = 102_400  # 100 KB (AC-17)

API_KEY_ENV = "ANTHROPIC_API_KEY"


def require_api_key() -> None:
    """Exit with a helpful message if no Anthropic API key is configured (AC-23)."""
    if os.environ.get(API_KEY_ENV, "").strip():
        return
    print(
        f"Error: {API_KEY_ENV} is not set.\n"
        f"Set it in your environment, or copy .env.example to .env and put your key there:\n"
        f"    {API_KEY_ENV}=sk-ant-...",
        file=sys.stderr,
    )
    sys.exit(1)


def ensure_knowledge_dir(path: Path = KNOWLEDGE_DIR) -> None:
    """Create the readable folder if it does not exist yet (AC-22)."""
    if path.exists() and not path.is_dir():
        print(
            f"Error: {path} exists but is not a folder. Move it away and restart.", file=sys.stderr
        )
        sys.exit(1)
    path.mkdir(parents=True, exist_ok=True)
