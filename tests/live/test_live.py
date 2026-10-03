"""End-to-end smoke tests against the real Claude API (costs a little money).

Run with: uv run pytest -m live
"""

import os
from pathlib import Path

import pytest
from anthropic.types.beta import BetaMessageParam
from dotenv import load_dotenv

from chat_agent.agent import Agent
from chat_agent.config import PROJECT_ROOT
from chat_agent.events import AgentEvent, ErrorEvent, Sources, TextDelta, ToolActivity
from chat_agent.knowledge import KnowledgeBase
from chat_agent.llm import AnthropicLLM

load_dotenv(PROJECT_ROOT / ".env")

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set"),
]


async def ask(agent: Agent, question: str) -> list[AgentEvent]:
    history: list[BetaMessageParam] = []
    return [event async for event in agent.run_turn(history, question)]


def answer_text(events: list[AgentEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextDelta))


async def test_ac12_ac13_current_events_question_searches_and_cites(tmp_path: Path) -> None:
    agent = Agent(AnthropicLLM(), KnowledgeBase(tmp_path))
    events = await ask(agent, "Search the web: what is the latest stable Python release? One line.")
    assert not [e for e in events if isinstance(e, ErrorEvent)]
    assert any(isinstance(e, ToolActivity) and e.kind == "web_search" for e in events)
    sources = [e for e in events if isinstance(e, Sources)]
    assert sources and all(s.url.startswith("http") for s in sources[0].items)
    assert answer_text(events)


async def test_ac16_question_about_knowledge_file_reads_it(tmp_path: Path) -> None:
    (tmp_path / "pets.md").write_text("My cat is called Zorbaflux.\n")
    agent = Agent(AnthropicLLM(), KnowledgeBase(tmp_path))
    events = await ask(agent, "What is my cat called? Check my files.")
    assert any(isinstance(e, ToolActivity) and e.kind == "read_file" for e in events)
    assert "Zorbaflux" in answer_text(events)
