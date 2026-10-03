from anthropic.types.beta import BetaMessageParam

from chat_agent.events import TextDelta, ToolActivity
from chat_agent.llm import FinalMessage, LLMClient
from tests.fakes import FakeLLM, message, server_search, text, tool_use


async def test_fake_llm_replays_script_and_records_requests() -> None:
    first = message(
        text("Let me look."), server_search("srv_1", "uv latest"), stop_reason="end_turn"
    )
    second = message(tool_use("tu_1", "read_file", {"path": "a.md"}), stop_reason="tool_use")
    fake = FakeLLM([first, second])
    client: LLMClient = fake  # the fake satisfies the protocol

    history: list[BetaMessageParam] = [{"role": "user", "content": "hi"}]
    events = [e async for e in client.stream(history, max_web_searches=7, tools_enabled=True)]
    history.append({"role": "assistant", "content": "changed later"})

    assert events[0] == TextDelta("Let me look.")
    assert events[1] == ToolActivity("web_search", "uv latest")
    assert events[-1] == FinalMessage(first)
    assert fake.requests[0].messages == [{"role": "user", "content": "hi"}]  # snapshot, not alias
    assert fake.requests[0].max_web_searches == 7
    assert fake.requests[0].tools_enabled is True

    events = [e async for e in client.stream(history, max_web_searches=6, tools_enabled=False)]
    assert events == [FinalMessage(second)]
    assert len(fake.requests) == 2


async def test_fake_llm_raises_scripted_exceptions() -> None:
    fake = FakeLLM([RuntimeError("boom")])
    try:
        _ = [e async for e in fake.stream([], max_web_searches=1, tools_enabled=True)]
    except RuntimeError as error:
        assert str(error) == "boom"
    else:
        raise AssertionError("expected RuntimeError")
