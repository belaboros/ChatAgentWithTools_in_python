"""HTTP layer: the chat page plus a JSON/SSE API (spec 001)."""

import dataclasses
import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from chat_agent.agent import Agent
from chat_agent.conversations import (
    Conversation,
    ConversationBusy,
    ConversationStore,
    UnknownConversation,
)
from chat_agent.events import AgentEvent, Done, ErrorEvent, Sources, TextDelta, ToolActivity

STATIC_DIR = Path(__file__).parent / "static"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Only this app's own files: no remote images, scripts, frames, or connections (AC-25).
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data:",
        "script-src 'self'",
        "style-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
SECURITY_HEADERS = [
    (b"content-security-policy", CONTENT_SECURITY_POLICY.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
]


class SecurityHeadersMiddleware:
    """Adds SECURITY_HEADERS to every response. Plain ASGI (not BaseHTTPMiddleware), so
    streaming replies and client disconnects pass through untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *SECURITY_HEADERS]
            await send(message)

        await self.app(scope, receive, send_with_headers)


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


def _sse(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


def _encode(event: AgentEvent) -> str:
    match event:
        case TextDelta(text=text):
            return _sse("text", {"text": text})
        case ToolActivity():
            return _sse("activity", dataclasses.asdict(event))
        case Sources():
            return _sse("sources", dataclasses.asdict(event))
        case ErrorEvent(message=message):
            return _sse("error", {"message": message})
        case Done():
            return _sse("done", {})


def create_app(agent: Agent, store: ConversationStore) -> FastAPI:
    app = FastAPI(title="Chat agent", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SecurityHeadersMiddleware)
    # AC-26: refuse requests addressed to any other host name. A malicious page could
    # otherwise rebind its own domain to 127.0.0.1 and use this API (DNS rebinding).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.post("/api/conversations")
    async def new_conversation() -> dict[str, str]:
        return {"id": store.new().id}

    @app.post("/api/chat")
    async def chat(request: ChatRequest) -> StreamingResponse:
        user_text = request.message.strip()
        if not user_text:
            raise HTTPException(400, "Message is empty.")  # AC-8
        try:
            conversation = store.get(request.conversation_id)
        except UnknownConversation:
            raise HTTPException(404, "Unknown conversation; start a new chat.") from None
        if conversation.busy:
            raise HTTPException(409, "A reply is still being generated.")  # AC-7
        return StreamingResponse(
            _stream(conversation, user_text),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    async def _stream(conversation: Conversation, user_text: str) -> AsyncIterator[str]:
        try:
            with conversation.turn():
                async for event in agent.run_turn(conversation.history, user_text):
                    yield _encode(event)
        except ConversationBusy:
            yield _encode(ErrorEvent("A reply is still being generated."))
            yield _encode(Done())

    return app
