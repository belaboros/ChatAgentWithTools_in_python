"""A scripted stand-in for the Claude API plus builders for SDK-shaped messages."""

import copy
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

import anthropic
import httpx2
from anthropic.types.beta import BetaMessage, BetaMessageParam

from chat_agent.events import TextDelta, ToolActivity
from chat_agent.llm import FinalMessage, LLMEvent


@dataclass
class Request:
    messages: list[Any]
    max_web_searches: int
    tools_enabled: bool


class FakeLLM:
    """Replays scripted messages (or raises scripted exceptions), one per `stream` call."""

    def __init__(self, script: Sequence[BetaMessage | Exception]) -> None:
        self.script = list(script)
        self.requests: list[Request] = []

    async def stream(
        self,
        messages: Sequence[BetaMessageParam],
        *,
        max_web_searches: int,
        tools_enabled: bool,
    ) -> AsyncIterator[LLMEvent]:
        self.requests.append(
            Request(copy.deepcopy(list(messages)), max_web_searches, tools_enabled)
        )
        if not self.script:
            raise AssertionError("FakeLLM script exhausted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        for block in item.content:
            if block.type == "text":
                yield TextDelta(block.text)
            elif block.type == "server_tool_use" and block.name == "web_search":
                yield ToolActivity("web_search", str(block.input.get("query", "")))
        yield FinalMessage(item)


_ids = iter(range(1, 1_000_000))


def text(value: str, citations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"type": "text", "text": value, "citations": citations}


def citation(url: str, title: str | None = None) -> dict[str, Any]:
    return {
        "type": "web_search_result_location",
        "url": url,
        "title": title,
        "cited_text": "...",
        "encrypted_index": "enc",
    }


def tool_use(id: str, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_use", "id": id, "name": name, "input": tool_input}


def server_search(id: str, query: str) -> dict[str, Any]:
    return {"type": "server_tool_use", "id": id, "name": "web_search", "input": {"query": query}}


def server_code(id: str) -> dict[str, Any]:
    return {"type": "server_tool_use", "id": id, "name": "code_execution", "input": {"code": "1"}}


def search_results(tool_use_id: str, *urls: str) -> dict[str, Any]:
    results = [
        {"type": "web_search_result", "url": url, "title": url, "encrypted_content": "enc"}
        for url in urls
    ]
    return {"type": "web_search_tool_result", "tool_use_id": tool_use_id, "content": results}


def search_error(tool_use_id: str, code: str = "unavailable") -> dict[str, Any]:
    return {
        "type": "web_search_tool_result",
        "tool_use_id": tool_use_id,
        "content": {"type": "web_search_tool_result_error", "error_code": code},
    }


def message(*blocks: dict[str, Any], stop_reason: str = "end_turn") -> BetaMessage:
    return BetaMessage.model_validate(
        {
            "id": f"msg_{next(_ids)}",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": list(blocks),
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    )


_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def api_status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    return cls(f"status {status}", response=httpx2.Response(status, request=_REQUEST), body=None)


def connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(request=_REQUEST)
