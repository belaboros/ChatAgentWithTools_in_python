"""The agent loop: one user message in, a stream of domain events out."""

import logging
from collections.abc import AsyncIterator

import anthropic
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaToolResultBlockParam,
    BetaToolUseBlock,
)

from chat_agent.config import MAX_TOOL_CALLS
from chat_agent.events import AgentEvent, Done, ErrorEvent, Source, Sources, ToolActivity
from chat_agent.knowledge import KnowledgeBase
from chat_agent.llm import FinalMessage, LLMClient
from chat_agent.tools import LIST_FILES, READ_FILE, run_client_tool

MAX_PAUSE_CONTINUATIONS = 5

logger = logging.getLogger(__name__)


class TurnFailed(Exception):
    """The turn cannot be completed; the message is shown to the user."""


def _error_message(error: Exception) -> str:
    """A readable message for the chat (AC-24). Never includes exception text (may hold secrets)."""
    match error:
        case TurnFailed():
            return str(error)
        case anthropic.AuthenticationError():
            return (
                "The Anthropic API key was rejected. Check ANTHROPIC_API_KEY and restart the app."
            )
        case anthropic.RateLimitError():
            return "The Claude API is rate-limiting requests right now. Wait a moment, then retry."
        case anthropic.APIStatusError():
            return f"The Claude API returned an error (status {error.status_code}). Please retry."
        case anthropic.APIConnectionError():
            return "Could not reach the Claude API. Check your internet connection and retry."
        case _:
            logger.exception("Unexpected error while answering")
            return "Something went wrong while answering. Please try again."


def _cited_sources(message: BetaMessage) -> list[Source]:
    return [
        Source(citation.url, citation.title)
        for block in message.content
        if block.type == "text"
        for citation in block.citations or []
        if citation.type == "web_search_result_location"
    ]


def _limit_note(limit: int) -> str:
    return (
        f"Tool-call limit reached ({limit} per message). No more tools are available for this "
        "message: give the best answer you can with the information you already have, and tell "
        "the user that you hit the tool-call limit."
    )


def _activity(block: BetaToolUseBlock) -> ToolActivity | None:
    path = block.input.get("path") if isinstance(block.input, dict) else None
    detail = path if isinstance(path, str) and path else ""
    if block.name == LIST_FILES:
        return ToolActivity("list_files", detail or "(top level)")
    if block.name == READ_FILE:
        return ToolActivity("read_file", detail)
    return None


class Agent:
    def __init__(self, llm: LLMClient, kb: KnowledgeBase, max_tool_calls: int = MAX_TOOL_CALLS):
        self.llm = llm
        self.kb = kb
        self.max_tool_calls = max_tool_calls

    async def run_turn(
        self, history: list[BetaMessageParam], user_text: str
    ) -> AsyncIterator[AgentEvent]:
        """Answer one user message, appending the exchange to `history` (append-only).

        If the turn fails, it is removed from `history` again, so the conversation stays valid
        and the user can simply send another message (AC-24).
        """
        start = len(history)
        completed = False
        try:
            async for event in self._answer(history, user_text):
                yield event
            completed = True
        except Exception as error:
            yield ErrorEvent(_error_message(error))
        finally:
            if not completed:
                del history[start:]
        yield Done()

    async def _answer(
        self, history: list[BetaMessageParam], user_text: str
    ) -> AsyncIterator[AgentEvent]:
        history.append({"role": "user", "content": user_text})
        budget = self.max_tool_calls  # shared by web searches and file tools (AC-11)
        sources: dict[str, Source] = {}  # by URL, in first-cited order (AC-13)
        pauses = 0
        while True:
            tools_enabled = budget > 0
            message: BetaMessage | None = None
            async for event in self.llm.stream(
                history, max_web_searches=budget, tools_enabled=tools_enabled
            ):
                if isinstance(event, FinalMessage):
                    message = event.message
                else:
                    yield event
            assert message is not None, "LLM stream ended without a final message"
            history.append({"role": "assistant", "content": message.content})
            budget -= sum(block.type == "server_tool_use" for block in message.content)
            for source in _cited_sources(message):
                sources.setdefault(source.url, source)

            if message.stop_reason == "pause_turn":
                # The server-side search loop paused; re-sending resumes it (no extra message).
                pauses += 1
                if pauses > MAX_PAUSE_CONTINUATIONS:
                    raise TurnFailed("The web search took too long and was stopped. Please retry.")
                continue
            pauses = 0
            if message.stop_reason == "refusal":
                raise TurnFailed("The model declined to answer this request.")

            tool_uses = [block for block in message.content if block.type == "tool_use"]
            if tool_uses and message.stop_reason == "max_tokens":
                # A truncated tool input can still parse as valid; never run it.
                raise TurnFailed("The answer got too long and was cut off. Please retry.")
            if message.stop_reason != "tool_use" or not tool_uses:
                break
            if not tools_enabled:
                # Unexpected with tool_choice "none": answer the calls so history stays valid.
                note = _limit_note(self.max_tool_calls)
                history.append(
                    {"role": "user", "content": [self._error_result(b, note) for b in tool_uses]}
                )
                break
            results: list[BetaContentBlockParam] = []
            for block in tool_uses:
                if budget <= 0:
                    # Every tool_use needs a result, even the ones over the limit.
                    results.append(self._error_result(block, _limit_note(self.max_tool_calls)))
                    continue
                budget -= 1
                if activity := _activity(block):
                    yield activity
                results.append(self._run_tool(block))
            if budget <= 0:
                results.append({"type": "text", "text": _limit_note(self.max_tool_calls)})
            # All results go back in ONE user message (keeps parallel tool use working).
            history.append({"role": "user", "content": results})
        if sources:
            yield Sources(tuple(sources.values()))

    @staticmethod
    def _error_result(block: BetaToolUseBlock, text: str) -> BetaToolResultBlockParam:
        return {"type": "tool_result", "tool_use_id": block.id, "content": text, "is_error": True}

    def _run_tool(self, block: BetaToolUseBlock) -> BetaToolResultBlockParam:
        output = run_client_tool(block.name, block.input, self.kb)
        result: BetaToolResultBlockParam = {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": output.content,
        }
        if output.is_error:
            result["is_error"] = True
        return result
