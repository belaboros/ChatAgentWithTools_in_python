"""Domain events the agent streams to the web layer (serialized as SSE)."""

from dataclasses import dataclass
from typing import Literal

ToolKind = Literal["web_search", "list_files", "read_file"]


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolActivity:
    """A tool the assistant is using, shown in the conversation (AC-9)."""

    kind: ToolKind
    detail: str  # the search query or the path


@dataclass(frozen=True)
class Source:
    url: str
    title: str | None = None


@dataclass(frozen=True)
class Sources:
    """Web sources the answer relied on (AC-13)."""

    items: tuple[Source, ...]


@dataclass(frozen=True)
class ErrorEvent:
    """A user-readable error; never contains secrets (AC-24)."""

    message: str


@dataclass(frozen=True)
class Done:
    pass


AgentEvent = TextDelta | ToolActivity | Sources | ErrorEvent | Done
