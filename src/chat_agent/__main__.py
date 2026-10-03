"""Entry point: `uv run chat-agent` (or `python -m chat_agent`)."""

import uvicorn
from dotenv import load_dotenv

from chat_agent.agent import Agent
from chat_agent.config import (
    HOST,
    KNOWLEDGE_DIR,
    PORT,
    PROJECT_ROOT,
    ensure_knowledge_dir,
    require_api_key,
)
from chat_agent.conversations import ConversationStore
from chat_agent.knowledge import KnowledgeBase
from chat_agent.llm import AnthropicLLM
from chat_agent.web import create_app


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    require_api_key()  # AC-23
    ensure_knowledge_dir(KNOWLEDGE_DIR)  # AC-22
    agent = Agent(AnthropicLLM(), KnowledgeBase(KNOWLEDGE_DIR))
    app = create_app(agent, ConversationStore())
    print(f"Chat agent running at http://{HOST}:{PORT}  (reading files from {KNOWLEDGE_DIR})")
    uvicorn.run(app, host=HOST, port=PORT)  # localhost only (AC-2)


if __name__ == "__main__":
    main()
