"""HTTP layer: the chat page plus a JSON/SSE API (spec 001)."""

import dataclasses
import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chat_agent.agent import Agent
from chat_agent.conversations import (
    Conversation,
    ConversationBusy,
    ConversationStore,
    UnknownConversation,
)
from chat_agent.events import AgentEvent, Done, ErrorEvent, Sources, TextDelta, ToolActivity

STATIC_DIR = Path(__file__).parent / "static"


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
