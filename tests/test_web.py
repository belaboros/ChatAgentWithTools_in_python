import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest
from anthropic.types.beta import BetaMessage

from chat_agent.agent import Agent
from chat_agent.conversations import ConversationStore
from chat_agent.knowledge import KnowledgeBase
from chat_agent.web import create_app
from tests.fakes import (
    FakeLLM,
    citation,
    connection_error,
    message,
    search_results,
    server_search,
    text,
    tool_use,
)


class App:
    def __init__(self, tmp_path: Path, script: Sequence[BetaMessage | Exception]) -> None:
        root = tmp_path / "knowledge"
        root.mkdir(exist_ok=True)
        (root / "a.md").write_text("A")
        self.llm = FakeLLM(script)
        self.store = ConversationStore()
        self.app = create_app(Agent(self.llm, KnowledgeBase(root)), self.store)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        )


@pytest.fixture
def make_app(tmp_path: Path) -> Any:
    return lambda *script: App(tmp_path, script)


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for chunk in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in chunk.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


async def new_conversation(client: httpx.AsyncClient) -> str:
    response = await client.post("/api/conversations")
    assert response.status_code == 200
    return response.json()["id"]


async def chat(client: httpx.AsyncClient, conversation_id: str, text_: str) -> httpx.Response:
    return await client.post(
        "/api/chat", json={"conversation_id": conversation_id, "message": text_}
    )


async def test_ac3_chat_streams_sse_text_then_done(make_app: Any) -> None:
    app = make_app(message(text("Hello "), text("world")))
    async with app.client() as client:
        conversation_id = await new_conversation(client)
        response = await chat(client, conversation_id, "Hi")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert parse_sse(response.text) == [
        ("text", {"text": "Hello "}),
        ("text", {"text": "world"}),
        ("done", {}),
    ]


async def test_ac5_new_conversation_has_no_memory(make_app: Any) -> None:
    app = make_app(message(text("one")), message(text("two")))
    async with app.client() as client:
        first = await new_conversation(client)
        await chat(client, first, "remember: 42")
        second = await new_conversation(client)
        await chat(client, second, "what did I say?")
    assert second != first
    assert app.llm.requests[1].messages == [{"role": "user", "content": "what did I say?"}]


async def test_ac4_same_conversation_keeps_history(make_app: Any) -> None:
    app = make_app(message(text("one")), message(text("two")))
    async with app.client() as client:
        conversation_id = await new_conversation(client)
        await chat(client, conversation_id, "first")
        await chat(client, conversation_id, "second")
    assert len(app.llm.requests[1].messages) == 3


async def test_ac7_concurrent_chat_returns_409(make_app: Any) -> None:
    app = make_app(message(text("never sent")))
    async with app.client() as client:
        conversation_id = await new_conversation(client)
        with app.store.get(conversation_id).turn():  # a reply is in progress
            response = await chat(client, conversation_id, "again")
    assert response.status_code == 409
    assert app.llm.requests == []


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
async def test_ac8_blank_message_returns_400(make_app: Any, blank: str) -> None:
    app = make_app()
    async with app.client() as client:
        conversation_id = await new_conversation(client)
        response = await chat(client, conversation_id, blank)
    assert response.status_code == 400
    assert app.llm.requests == []


async def test_unknown_conversation_404(make_app: Any) -> None:
    app = make_app()
    async with app.client() as client:
        response = await chat(client, "does-not-exist", "hi")
    assert response.status_code == 404


async def test_ac9_activity_events_serialized(make_app: Any) -> None:
    app = make_app(
        message(
            server_search("srv_1", "news"),
            search_results("srv_1", "https://n.example"),
            tool_use("tu_1", "read_file", {"path": "a.md"}),
            stop_reason="tool_use",
        ),
        message(text("ok")),
    )
    async with app.client() as client:
        response = await chat(client, await new_conversation(client), "go")
    activities = [data for name, data in parse_sse(response.text) if name == "activity"]
    assert activities == [
        {"kind": "web_search", "detail": "news"},
        {"kind": "read_file", "detail": "a.md"},
    ]


async def test_ac13_sources_event_serialized(make_app: Any) -> None:
    app = make_app(message(text("x", citations=[citation("https://s.example", "S")])))
    async with app.client() as client:
        response = await chat(client, await new_conversation(client), "go")
    events = parse_sse(response.text)
    assert ("sources", {"items": [{"url": "https://s.example", "title": "S"}]}) in events
    assert events[-1] == ("done", {})


async def test_ac24_error_event_then_done(make_app: Any) -> None:
    app = make_app(connection_error(), message(text("recovered")))
    async with app.client() as client:
        conversation_id = await new_conversation(client)
        failed = parse_sse((await chat(client, conversation_id, "hi")).text)
        recovered = parse_sse((await chat(client, conversation_id, "hi again")).text)
    assert [name for name, _ in failed] == ["error", "done"]
    assert "reach" in failed[0][1]["message"].lower()
    assert recovered == [("text", {"text": "recovered"}), ("done", {})]


async def test_ac1_page_has_chat_controls(make_app: Any) -> None:
    async with make_app().client() as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    for control in [
        'id="message-input"',
        'id="send-button"',
        'id="new-chat-button"',
        'id="messages"',
    ]:
        assert control in html, control
    assert "New chat" in html


async def test_ac25_page_loads_sanitizer_and_markdown(make_app: Any) -> None:
    async with make_app().client() as client:
        html = (await client.get("/")).text
        scripts = ["/static/vendor/marked.umd.js", "/static/vendor/purify.min.js", "/static/app.js"]
        for src in scripts:
            assert f'src="{src}"' in html, src
            assert (await client.get(src)).status_code == 200, src
        app_js = (await client.get("/static/app.js")).text
    # Markdown output is always sanitized before it is inserted into the page.
    assert "DOMPurify.sanitize(marked.parse(" in app_js
    assert html.index("purify.min.js") < html.index("app.js")
    assert html.index("marked.umd.js") < html.index("app.js")
