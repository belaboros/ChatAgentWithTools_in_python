"""The only module that talks to the Claude API (test seam: `LLMClient`)."""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from anthropic import AsyncAnthropic, Omit, omit
from anthropic.types.beta import BetaMessage, BetaMessageParam, BetaToolChoiceParam

from chat_agent.config import MODEL
from chat_agent.events import TextDelta, ToolActivity
from chat_agent.prompts import SYSTEM_PROMPT
from chat_agent.tools import WEB_SEARCH, tool_definitions

MAX_TOKENS = 64_000  # streaming, so no HTTP-timeout concern
EFFORT = "medium"  # Sonnet 5.5's recommended starting point for multi-step tool use


@dataclass(frozen=True)
class FinalMessage:
    """Always the last event of a stream: the complete assistant message."""

    message: BetaMessage


LLMEvent = TextDelta | ToolActivity | FinalMessage


class LLMClient(Protocol):
    def stream(
        self,
        messages: Sequence[BetaMessageParam],
        *,
        max_web_searches: int,
        tools_enabled: bool,
    ) -> AsyncIterator[LLMEvent]:
        """Stream one model response: text deltas and web-search activity, then FinalMessage."""
        ...


class AnthropicLLM:
    """`LLMClient` backed by the Claude API (streaming, beta namespace for `fallbacks`)."""

    def __init__(self, client: AsyncAnthropic | None = None, model: str = MODEL) -> None:
        self.client = client or AsyncAnthropic()
        self.model = model

    async def stream(
        self,
        messages: Sequence[BetaMessageParam],
        *,
        max_web_searches: int,
        tools_enabled: bool,
    ) -> AsyncIterator[LLMEvent]:
        # Out of tool budget: still send the (cache-stable) tools, but forbid using them.
        tool_choice: BetaToolChoiceParam | Omit = omit if tools_enabled else {"type": "none"}
        for attempt in range(2):
            yielded = False
            try:
                async with self.client.beta.messages.stream(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    tools=tool_definitions(max_web_searches),
                    tool_choice=tool_choice,
                    output_config={"effort": EFFORT},
                    cache_control={"type": "ephemeral"},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                ) as stream:
                    async for event in stream:
                        if event.type == "text":
                            yielded = True
                            yield TextDelta(event.text)
                        elif event.type == "content_block_stop":
                            block = event.content_block
                            if block.type == "server_tool_use" and block.name == WEB_SEARCH:
                                yielded = True
                                query = (
                                    block.input.get("query")
                                    if isinstance(block.input, dict)
                                    else None
                                )
                                yield ToolActivity("web_search", str(query or ""))
                    message = await stream.get_final_message()
            except ValueError:
                # Eager tool-input streaming: the SDK could not parse a tool input at all.
                # Re-issue once, but only if nothing reached the user yet (no duplicated text).
                if attempt or yielded:
                    raise
                continue
            yield FinalMessage(message)
            return
