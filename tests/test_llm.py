import json
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic
from anthropic.types.beta import BetaMessageParam

from chat_agent.events import TextDelta, ToolActivity
from chat_agent.llm import AnthropicLLM, FinalMessage, LLMEvent
from chat_agent.prompts import SYSTEM_PROMPT
from tests.fakes import citation, search_error, search_results, server_search, text, tool_use
from tests.sse import sse_body


class MockAPI:
    """Records request bodies and answers each with the next scripted SSE body."""

    def __init__(self, *bodies: bytes | httpx2.Response) -> None:
        self.bodies = list(bodies)
        self.requests: list[dict[str, Any]] = []
        self.headers: list[httpx2.Headers] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        self.headers.append(request.headers)
        body = self.bodies.pop(0)
        if isinstance(body, httpx2.Response):
            return body
        return httpx2.Response(200, content=body, headers={"content-type": "text/event-stream"})

    def llm(self) -> AnthropicLLM:
        http = httpx2.AsyncClient(transport=httpx2.MockTransport(self.handler))
        return AnthropicLLM(AsyncAnthropic(api_key="sk-test", http_client=http, max_retries=0))


USER: list[BetaMessageParam] = [{"role": "user", "content": "hi"}]


async def collect(
    llm: AnthropicLLM, messages: list[BetaMessageParam] = USER, **kwargs: Any
) -> list[LLMEvent]:
    kwargs = {"max_web_searches": 10, "tools_enabled": True, **kwargs}
    return [event async for event in llm.stream(messages, **kwargs)]


async def test_request_settings() -> None:
    api = MockAPI(sse_body(text("Hello")))
    await collect(api.llm())
    body = api.requests[0]
    assert body["model"] == "claude-sonnet-5-5"
    assert body["max_tokens"] == 64000
    assert body["stream"] is True
    assert body["system"] == SYSTEM_PROMPT
    assert body["output_config"] == {"effort": "medium"}
    assert body["cache_control"] == {"type": "ephemeral"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in api.headers[0]["anthropic-beta"]
    assert "tool_choice" not in body


async def test_ac12_request_includes_web_search_tool() -> None:
    api = MockAPI(sse_body(text("Hello")))
    await collect(api.llm())
    tools = {tool["name"]: tool for tool in api.requests[0]["tools"]}
    assert set(tools) == {"web_search", "list_files", "read_file"}
    assert tools["web_search"]["type"] == "web_search_20260209"


async def test_ac11_max_uses_set_from_budget() -> None:
    api = MockAPI(sse_body(text("Hello")))
    await collect(api.llm(), max_web_searches=3)
    (web_search,) = [t for t in api.requests[0]["tools"] if t["name"] == "web_search"]
    assert web_search["max_uses"] == 3


async def test_ac11_tools_disabled_sets_tool_choice_none() -> None:
    api = MockAPI(sse_body(text("Hello")))
    await collect(api.llm(), max_web_searches=0, tools_enabled=False)
    assert api.requests[0]["tool_choice"] == {"type": "none"}


async def test_stream_events_translated() -> None:
    api = MockAPI(
        sse_body(
            text("Let me search. "),
            server_search("srv_1", "uv release"),
            search_results("srv_1", "https://docs.astral.sh"),
            text("uv is great.", citations=[citation("https://docs.astral.sh", "uv")]),
            tool_use("tu_1", "read_file", {"path": "notes/a.md"}),
            stop_reason="tool_use",
        )
    )
    events = await collect(api.llm())
    deltas = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert deltas == "Let me search. uv is great."
    assert [e for e in events if isinstance(e, ToolActivity)] == [
        ToolActivity("web_search", "uv release")
    ]
    final = events[-1]
    assert isinstance(final, FinalMessage)
    assert final.message.stop_reason == "tool_use"
    types = [block.type for block in final.message.content]
    assert types == ["text", "server_tool_use", "web_search_tool_result", "text", "tool_use"]
    cited = final.message.content[3]
    assert cited.type == "text" and cited.citations
    assert cited.citations[0].type == "web_search_result_location"


async def test_ac14_search_error_block_passed_through() -> None:
    api = MockAPI(
        sse_body(server_search("srv_1", "q"), search_error("srv_1"), text("Search failed."))
    )
    events = await collect(api.llm())
    final = events[-1]
    assert isinstance(final, FinalMessage)
    assert final.message.content[1].type == "web_search_tool_result"


async def test_history_with_sdk_blocks_is_sent_back() -> None:
    api = MockAPI(
        sse_body(server_search("srv_1", "q"), stop_reason="pause_turn"), sse_body(text("ok"))
    )
    llm = api.llm()
    first = await collect(llm)
    final = first[-1]
    assert isinstance(final, FinalMessage)
    history: list[BetaMessageParam] = [
        *USER,
        {"role": "assistant", "content": final.message.content},
    ]
    await collect(llm, history)
    sent = api.requests[1]["messages"][1]
    assert sent["role"] == "assistant"
    assert sent["content"][0]["type"] == "server_tool_use"
    assert sent["content"][0]["input"] == {"query": "q"}


async def test_api_errors_propagate() -> None:
    import anthropic

    api = MockAPI(
        httpx2.Response(
            401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad"}}
        )
    )
    with pytest.raises(anthropic.AuthenticationError):
        await collect(api.llm())


def _garbled_tool_input_body() -> bytes:
    body = sse_body(tool_use("tu_1", "read_file", {"path": "a.md"}), stop_reason="tool_use")
    return body.replace(b'{\\"path\\": \\"a.md\\"}', b"}}not json{{")


async def test_unparseable_tool_input_is_retried_once() -> None:
    api = MockAPI(_garbled_tool_input_body(), sse_body(text("ok")))
    events = await collect(api.llm())
    assert len(api.requests) == 2
    assert isinstance(events[-1], FinalMessage)
    assert "".join(e.text for e in events if isinstance(e, TextDelta)) == "ok"


async def test_unparseable_tool_input_twice_raises() -> None:
    api = MockAPI(_garbled_tool_input_body(), _garbled_tool_input_body())
    with pytest.raises(ValueError):
        await collect(api.llm())
