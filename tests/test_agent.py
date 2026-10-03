from collections.abc import Sequence
from pathlib import Path
from typing import Any

import anthropic
import pytest
from anthropic.types.beta import BetaMessage, BetaMessageParam

from chat_agent.agent import Agent
from chat_agent.events import (
    AgentEvent,
    Done,
    ErrorEvent,
    Source,
    Sources,
    TextDelta,
    ToolActivity,
)
from chat_agent.knowledge import KnowledgeBase
from tests.fakes import (
    FakeLLM,
    api_status_error,
    citation,
    connection_error,
    message,
    search_error,
    search_results,
    server_search,
    text,
    tool_use,
)


@pytest.fixture
def kb(tmp_path: Path) -> KnowledgeBase:
    root = tmp_path / "knowledge"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "todo.md").write_text("- buy milk")
    return KnowledgeBase(root)


def make_agent(
    kb: KnowledgeBase, script: Sequence[BetaMessage | Exception], **kwargs: Any
) -> tuple[Agent, FakeLLM]:
    fake = FakeLLM(script)
    return Agent(fake, kb, **kwargs), fake


async def run(agent: Agent, history: list[BetaMessageParam], user_text: str) -> list[AgentEvent]:
    return [event async for event in agent.run_turn(history, user_text)]


def roles(history: list[BetaMessageParam]) -> list[str]:
    return [m["role"] for m in history]


async def test_ac3_streams_text_deltas_then_done(kb: KnowledgeBase) -> None:
    agent, _ = make_agent(kb, [message(text("Hello "), text("there!"))])
    history: list[BetaMessageParam] = []
    events = await run(agent, history, "Hi")
    assert events == [TextDelta("Hello "), TextDelta("there!"), Done()]
    assert roles(history) == ["user", "assistant"]
    assert history[0] == {"role": "user", "content": "Hi"}


async def test_ac4_second_turn_includes_history(kb: KnowledgeBase) -> None:
    first = message(text("Your name is Bela."))
    agent, fake = make_agent(kb, [first, message(text("You told me: Bela."))])
    history: list[BetaMessageParam] = []
    await run(agent, history, "My name is Bela.")
    await run(agent, history, "What is my name?")
    sent = fake.requests[1].messages
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[0]["content"] == "My name is Bela."
    assert sent[1]["content"] == first.content  # assistant content kept verbatim
    assert sent[2]["content"] == "What is my name?"


def tool_results(entry: BetaMessageParam) -> list[dict[str, Any]]:
    assert entry["role"] == "user"
    content = entry["content"]
    assert isinstance(content, list)
    return [dict(block) for block in content]  # type: ignore[arg-type]


async def test_ac9_tool_activity_events_in_order(kb: KnowledgeBase) -> None:
    script = [
        message(
            text("Checking."),
            tool_use("tu_1", "list_files", {"path": ""}),
            tool_use("tu_2", "read_file", {"path": "notes/todo.md"}),
            stop_reason="tool_use",
        ),
        message(text("You need milk.")),
    ]
    agent, _ = make_agent(kb, script)
    events = await run(agent, [], "What is on my todo list?")
    assert events == [
        TextDelta("Checking."),
        ToolActivity("list_files", "(top level)"),
        ToolActivity("read_file", "notes/todo.md"),
        TextDelta("You need milk."),
        Done(),
    ]


async def test_ac10_list_then_read_then_answer(kb: KnowledgeBase) -> None:
    script = [
        message(tool_use("tu_1", "list_files", {"path": "notes"}), stop_reason="tool_use"),
        message(tool_use("tu_2", "read_file", {"path": "notes/todo.md"}), stop_reason="tool_use"),
        message(text("Buy milk.")),
    ]
    agent, fake = make_agent(kb, script)
    history: list[BetaMessageParam] = []
    events = await run(agent, history, "todo?")
    assert events[-2:] == [TextDelta("Buy milk."), Done()]
    assert roles(history) == ["user", "assistant", "user", "assistant", "user", "assistant"]
    assert tool_results(history[2]) == [
        {"type": "tool_result", "tool_use_id": "tu_1", "content": "notes/todo.md"}
    ]
    assert tool_results(history[4]) == [
        {"type": "tool_result", "tool_use_id": "tu_2", "content": "- buy milk"}
    ]
    assert len(fake.requests) == 3


async def test_parallel_tool_results_in_single_message(kb: KnowledgeBase) -> None:
    script = [
        message(
            tool_use("tu_1", "read_file", {"path": "notes/todo.md"}),
            tool_use("tu_2", "read_file", {"path": "missing.md"}),
            stop_reason="tool_use",
        ),
        message(text("ok")),
    ]
    agent, _ = make_agent(kb, script)
    history: list[BetaMessageParam] = []
    await run(agent, history, "read both")
    results = tool_results(history[2])
    assert [r["tool_use_id"] for r in results] == ["tu_1", "tu_2"]
    assert "is_error" not in results[0]
    assert results[1]["is_error"] is True


async def test_ac11_eleventh_call_rejected_and_tools_disabled(kb: KnowledgeBase) -> None:
    calls = [tool_use(f"tu_{i}", "read_file", {"path": "notes/todo.md"}) for i in range(11)]
    script = [message(*calls, stop_reason="tool_use"), message(text("I hit the tool limit."))]
    agent, fake = make_agent(kb, script)
    history: list[BetaMessageParam] = []
    events = await run(agent, history, "read it 11 times")

    results = tool_results(history[2])
    tool_result_blocks = [r for r in results if r["type"] == "tool_result"]
    assert len(tool_result_blocks) == 11
    assert all("is_error" not in r for r in tool_result_blocks[:10])
    assert tool_result_blocks[10]["is_error"] is True
    assert "limit" in tool_result_blocks[10]["content"].lower()
    notes = [r for r in results if r["type"] == "text"]
    assert len(notes) == 1 and "limit" in notes[0]["text"].lower()

    assert fake.requests[0].tools_enabled is True
    assert fake.requests[1].tools_enabled is False
    assert sum(isinstance(e, ToolActivity) for e in events) == 10
    assert events[-1] == Done()


async def test_ac11_web_searches_count_against_budget(kb: KnowledgeBase) -> None:
    searches = []
    for i in range(3):
        searches += [
            server_search(f"srv_{i}", f"q{i}"),
            search_results(f"srv_{i}", "https://a.example"),
        ]
    script = [
        message(*searches, tool_use("tu_1", "list_files", {}), stop_reason="tool_use"),
        message(text("done")),
    ]
    agent, fake = make_agent(kb, script)
    await run(agent, [], "search a lot")
    assert fake.requests[0].max_web_searches == 10
    assert fake.requests[1].max_web_searches == 6  # 10 - 3 searches - 1 file listing


async def test_ac11_budget_resets_per_user_message(kb: KnowledgeBase) -> None:
    script = [
        message(tool_use("tu_1", "list_files", {}), stop_reason="tool_use"),
        message(text("first")),
        message(text("second")),
    ]
    agent, fake = make_agent(kb, script)
    history: list[BetaMessageParam] = []
    await run(agent, history, "one")
    await run(agent, history, "two")
    assert fake.requests[2].max_web_searches == 10
    assert fake.requests[2].tools_enabled is True


async def test_ac11_tool_call_with_tools_disabled_is_answered_not_run(kb: KnowledgeBase) -> None:
    calls = [tool_use(f"tu_{i}", "list_files", {}) for i in range(10)]
    script = [
        message(*calls, stop_reason="tool_use"),
        message(tool_use("tu_x", "read_file", {"path": "notes/todo.md"}), stop_reason="tool_use"),
    ]
    agent, fake = make_agent(kb, script)
    history: list[BetaMessageParam] = []
    events = await run(agent, history, "go")
    assert len(fake.requests) == 2
    assert events[-1] == Done()
    (result,) = tool_results(history[-1])
    assert result["tool_use_id"] == "tu_x"
    assert result["is_error"] is True


async def test_ac12_server_search_results_flow_into_answer(kb: KnowledgeBase) -> None:
    answer = message(
        server_search("srv_1", "python latest version"),
        search_results("srv_1", "https://python.org"),
        text("Python 3.14 is current.", citations=[citation("https://python.org", "Python")]),
    )
    agent, _ = make_agent(kb, [answer])
    history: list[BetaMessageParam] = []
    events = await run(agent, history, "Latest Python?")
    assert events == [
        ToolActivity("web_search", "python latest version"),
        TextDelta("Python 3.14 is current."),
        Sources((Source("https://python.org", "Python"),)),
        Done(),
    ]
    assert history[1]["content"] == answer.content


async def test_ac12_pause_turn_is_resumed(kb: KnowledgeBase) -> None:
    script = [
        message(server_search("srv_1", "q"), stop_reason="pause_turn"),
        message(search_results("srv_1", "https://a.example"), text("Found it.")),
    ]
    agent, fake = make_agent(kb, script)
    history: list[BetaMessageParam] = []
    events = await run(agent, history, "search")
    assert len(fake.requests) == 2
    assert fake.requests[1].messages[-1]["role"] == "assistant"  # no "continue" message added
    assert events[-2:] == [TextDelta("Found it."), Done()]


async def test_pause_turn_continuations_are_capped(kb: KnowledgeBase) -> None:
    script = [message(text("..."), stop_reason="pause_turn") for _ in range(10)]
    agent, fake = make_agent(kb, script)
    events = await run(agent, [], "search forever")
    assert len(fake.requests) == 6  # first request + 5 continuations
    assert isinstance(events[-2], ErrorEvent)
    assert events[-1] == Done()


async def test_ac13_citations_become_deduplicated_sources(kb: KnowledgeBase) -> None:
    a, b = citation("https://a.example", "A"), citation("https://b.example", "B")
    script = [
        message(
            text("One.", citations=[a]), tool_use("tu_1", "list_files", {}), stop_reason="tool_use"
        ),
        message(text("Two.", citations=[b, a])),
    ]
    agent, _ = make_agent(kb, script)
    events = await run(agent, [], "q")
    (sources,) = [e for e in events if isinstance(e, Sources)]
    assert sources.items == (Source("https://a.example", "A"), Source("https://b.example", "B"))
    assert events[-1] == Done()


async def test_ac13_no_sources_event_without_citations(kb: KnowledgeBase) -> None:
    agent, _ = make_agent(kb, [message(text("plain"))])
    events = await run(agent, [], "q")
    assert not any(isinstance(e, Sources) for e in events)


async def test_ac14_search_error_result_does_not_break_turn(kb: KnowledgeBase) -> None:
    script = [
        message(
            server_search("srv_1", "q"),
            search_error("srv_1"),
            text("Sorry, the web search did not work."),
        )
    ]
    agent, _ = make_agent(kb, script)
    events = await run(agent, [], "search")
    assert events == [
        ToolActivity("web_search", "q"),
        TextDelta("Sorry, the web search did not work."),
        Done(),
    ]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (api_status_error(anthropic.AuthenticationError, 401), "API key"),
        (api_status_error(anthropic.RateLimitError, 429), "rate"),
        (api_status_error(anthropic.InternalServerError, 529), "status 529"),
        (connection_error(), "reach"),
        (RuntimeError("secret internals sk-ant-123"), "went wrong"),
    ],
)
async def test_ac24_sdk_errors_map_to_readable_messages(
    kb: KnowledgeBase, error: Exception, expected: str
) -> None:
    agent, _ = make_agent(kb, [error])
    events = await run(agent, [], "hi")
    assert len(events) == 2
    assert isinstance(events[0], ErrorEvent)
    assert expected.lower() in events[0].message.lower()
    assert "sk-ant" not in events[0].message
    assert events[1] == Done()


async def test_ac24_history_rolled_back_on_error(kb: KnowledgeBase) -> None:
    history: list[BetaMessageParam] = []
    agent, _ = make_agent(
        kb,
        [
            message(text("ok")),
            message(tool_use("tu_1", "list_files", {}), stop_reason="tool_use"),
            connection_error(),
        ],
    )
    await run(agent, history, "first")
    before = list(history)
    events = await run(agent, history, "second")
    assert isinstance(events[-2], ErrorEvent)
    assert history == before  # the failed turn left no trace


async def test_ac24_next_turn_succeeds_after_error(kb: KnowledgeBase) -> None:
    history: list[BetaMessageParam] = []
    agent, fake = make_agent(kb, [connection_error(), message(text("Back again."))])
    await run(agent, history, "first")
    events = await run(agent, history, "second")
    assert events == [TextDelta("Back again."), Done()]
    assert fake.requests[1].messages == [{"role": "user", "content": "second"}]


async def test_refusal_reports_error(kb: KnowledgeBase) -> None:
    history: list[BetaMessageParam] = []
    agent, _ = make_agent(kb, [message(stop_reason="refusal")])
    events = await run(agent, history, "something declined")
    assert isinstance(events[0], ErrorEvent)
    assert "declined" in events[0].message.lower()
    assert events[-1] == Done()
    assert history == []


async def test_truncated_tool_input_not_executed(kb: KnowledgeBase) -> None:
    history: list[BetaMessageParam] = []
    truncated = message(
        tool_use("tu_1", "read_file", {"path": "notes/to"}), stop_reason="max_tokens"
    )
    agent, fake = make_agent(kb, [truncated])
    events = await run(agent, history, "read")
    assert not any(isinstance(e, ToolActivity) for e in events)
    assert isinstance(events[-2], ErrorEvent)
    assert len(fake.requests) == 1
    assert history == []


async def test_truncated_text_answer_is_kept(kb: KnowledgeBase) -> None:
    history: list[BetaMessageParam] = []
    agent, _ = make_agent(kb, [message(text("A very long answ"), stop_reason="max_tokens")])
    events = await run(agent, history, "long please")
    assert events == [TextDelta("A very long answ"), Done()]
    assert roles(history) == ["user", "assistant"]
