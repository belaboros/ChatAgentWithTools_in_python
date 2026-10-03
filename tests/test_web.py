import asyncio
import json
import re
import socket
import threading
import time
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from anthropic.types.beta import BetaMessage

from chat_agent.agent import Agent
from chat_agent.conversations import ConversationStore
from chat_agent.events import AgentEvent, ErrorEvent, Source, Sources, TextDelta, ToolActivity
from chat_agent.knowledge import KnowledgeBase
from chat_agent.llm import FinalMessage, LLMEvent
from chat_agent.web import _encode, create_app
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

    def client(self, base_url: str = "http://127.0.0.1:8000") -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=base_url)


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


async def test_ac25_every_inner_html_is_sanitized_without_images(make_app: Any) -> None:
    async with make_app().client() as client:
        app_js = (await client.get("/static/app.js")).text
    assignments = re.findall(r"\.innerHTML\s*=\s*(.+);", app_js)
    assert assignments, "expected the Markdown rendering assignment"
    for value in assignments:
        assert value.startswith("DOMPurify.sanitize(") and "SANITIZE_OPTIONS" in value, value
    for forbidden in ("insertAdjacentHTML", "outerHTML", "document.write"):
        assert forbidden not in app_js
    options = re.search(r"const SANITIZE_OPTIONS = (\{.*?\});", app_js, re.S)
    assert options is not None
    for tag in ("img", "picture", "source", "video", "audio", "svg"):
        assert f'"{tag}"' in options.group(1), tag  # nothing in a reply may load remote content


@pytest.mark.parametrize("path", ["/", "/static/app.js", "/api/conversations"])
async def test_ac25_csp_header(make_app: Any, path: str) -> None:
    async with make_app().client() as client:
        response = await (client.post(path) if path.startswith("/api") else client.get(path))
    csp = response.headers["content-security-policy"]
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";") if d.strip())
    assert directives["default-src"] == "'self'"
    assert directives["img-src"] == "'self' data:"  # no remote images
    assert directives["script-src"] == "'self'"  # no inline or remote scripts
    assert directives["connect-src"] == "'self'"
    assert directives["object-src"] == "'none'"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "192.168.1.20:8000", "test"])
async def test_ac26_foreign_host_rejected(make_app: Any, host: str) -> None:
    app = make_app(message(text("never")))
    async with app.client() as client:
        headers = {"host": host}
        page = await client.get("/", headers=headers)
        new = await client.post("/api/conversations", headers=headers)
        conversation_id = await new_conversation(client)  # legitimate host
        chat_response = await client.post(
            "/api/chat",
            json={"conversation_id": conversation_id, "message": "read my files"},
            headers=headers,
        )
    assert page.status_code == new.status_code == chat_response.status_code == 400
    assert app.llm.requests == []
    assert len(app.store._conversations) == 1  # only the legitimate one


@pytest.mark.parametrize(
    "base_url",
    ["http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1", "http://localhost"],
)
async def test_ac26_local_hosts_accepted(make_app: Any, base_url: str) -> None:
    async with make_app().client(base_url) as client:
        assert (await client.get("/")).status_code == 200
        assert (await client.post("/api/conversations")).status_code == 200


class BlockingLLM:
    """Streams one text delta, then waits until released (or forever)."""

    def __init__(self) -> None:
        self.calls = 0
        self.release = asyncio.Event()

    async def stream(
        self, messages: Sequence[Any], *, max_web_searches: int, tools_enabled: bool
    ) -> AsyncIterator[LLMEvent]:
        self.calls += 1
        yield TextDelta("partial ")
        await self.release.wait()
        yield FinalMessage(message(text("partial answer")))


async def test_ac7_simultaneous_requests_only_one_runs(tmp_path: Path) -> None:
    llm = BlockingLLM()
    store = ConversationStore()
    app = create_app(Agent(llm, KnowledgeBase(tmp_path)), store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        conversation_id = await new_conversation(client)

        async def post() -> httpx.Response:
            return await chat(client, conversation_id, "hi")

        first, second = asyncio.create_task(post()), asyncio.create_task(post())
        await asyncio.sleep(0.2)
        llm.release.set()
        responses = await asyncio.gather(first, second)
    assert llm.calls == 1  # the model was asked once
    outcomes = sorted(
        "rejected"
        if r.status_code == 409
        or any(name == "error" for name, _ in parse_sse(r.text))  # in-stream guard
        else "answered"
        for r in responses
    )
    assert outcomes == ["answered", "rejected"]
    assert store.get(conversation_id).busy is False


def _serve(app: Any) -> tuple[uvicorn.Server, threading.Thread, int]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started
    return server, thread, port


def _wait_for(condition: Any, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_ac24_disconnect_rolls_back_and_releases(tmp_path: Path) -> None:
    llm = BlockingLLM()  # never released: the reply hangs until the browser goes away
    store = ConversationStore()
    server, thread, port = _serve(create_app(Agent(llm, KnowledgeBase(tmp_path)), store))
    try:
        base = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=base) as client:
            conversation = store.get(client.post("/api/conversations").json()["id"])
            body = {"conversation_id": conversation.id, "message": "hi"}
            with client.stream("POST", "/api/chat", json=body) as response:
                first_chunk = next(response.iter_text())
                assert "partial" in first_chunk
                assert conversation.busy
            # Leaving the block closes the connection mid-reply ("New chat", closing the tab).
        assert _wait_for(lambda: not conversation.busy), "conversation stayed busy"
        assert conversation.history == []  # the unfinished turn was rolled back
    finally:
        server.should_exit = True
        thread.join(timeout=5)


async def test_ac6_page_starts_new_conversation_on_load(make_app: Any) -> None:
    async with make_app().client() as client:
        app_js = (await client.get("/static/app.js")).text
    body = re.search(r"async function newConversation\(\) \{(.*?)\n\}", app_js, re.S)
    assert body is not None
    assert "messages.replaceChildren()" in body.group(1)
    assert 'fetch("/api/conversations", { method: "POST" })' in body.group(1)
    assert app_js.rstrip().endswith("newConversation();")  # runs on every page load
    assert 'newChatButton.addEventListener("click", newConversation)' in app_js  # AC-5


@pytest.mark.parametrize(
    "event",
    [
        TextDelta("hi"),
        ToolActivity("read_file", "a.md"),
        Sources((Source("https://a.example", "A"),)),
        ErrorEvent("boom"),
    ],
)
async def test_ac3_page_unpacks_every_server_event(make_app: Any, event: AgentEvent) -> None:
    """Contract between web.py and app.js: each SSE event's JSON fields are destructured by the
    page's handler of the same name (a plain parameter would render "[object Object]")."""
    async with make_app().client() as client:
        app_js = (await client.get("/static/app.js")).text
    (name, data) = parse_sse(_encode(event))[0]
    fields = ", ".join(data)
    assert f"    {name}({{ {fields} }}) {{" in app_js, f"{name} handler must take {{ {fields} }}"
